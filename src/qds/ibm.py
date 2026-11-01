"""IBM Quantum kapcsolat és token-kezelés.

A token **soha** nem kerül a repóba. A feloldási sorrend (minden helyen
ugyanaz):

1. explicit ``token`` paraméter,
2. ``IBM_TOKEN_PATH`` környezeti változó,
3. a repository gyökerében lévő ``ibm_token.json`` (``.gitignore``-ban).

A fájl formátuma: ``{"apikey": "..."}``
"""

import json
import os

CHANNEL = "ibm_quantum_platform"


def token_path():
    """A token-fájl feloldott útvonala (még nem ellenőrzi a létezését)."""
    here = os.path.dirname(os.path.abspath(__file__))
    default = os.path.normpath(os.path.join(here, "..", "..", "ibm_token.json"))
    return os.environ.get("IBM_TOKEN_PATH", default)


def load_token(path=None):
    """Beolvassa az IBM API-kulcsot a token-fájlból.

    Raises:
        FileNotFoundError: ha a fájl nem létezik — a hibaüzenet megmondja,
            mit kell tenni.
        ValueError: ha a fájlban nincs ``apikey`` kulcs.
    """
    path = path or token_path()
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Nincs token-fájl: {path}\n"
            "Hozz létre egy ibm_token.json-t a repo gyökerében "
            '({"apikey": "..."}), vagy állítsd be az IBM_TOKEN_PATH-t. '
            "A fájl .gitignore-olt, a kulcs soha ne kerüljön commitba."
        )
    with open(path, encoding="utf-8") as f:
        creds = json.load(f)
    token = creds.get("apikey")
    if not token:
        raise ValueError(f"Nincs 'apikey' kulcs ebben: {path}")
    return token


def service(token=None, channel=CHANNEL):
    """Visszaad egy bejelentkezett ``QiskitRuntimeService``-t."""
    from qiskit_ibm_runtime import QiskitRuntimeService

    return QiskitRuntimeService(channel=channel, token=token or load_token(),
                                instance="auto")


def get_backend(name, token=None):
    """A megadott nevű backend (a token-feloldás a :func:`load_token` szerint)."""
    return service(token).backend(name=name)


def sampler(mode):
    """Visszaad egy Sampler-t a megadott backend/target módban.

    A qiskit-ibm-runtime 0.50-től a ``SamplerV2`` deprecated; az új kliensoldali
    ``qiskit_ibm_runtime.executor_sampler.Sampler``-t használjuk, és csak régi
    verzióknál esünk vissza a ``SamplerV2``-re. Mindkettő ugyanazt a
    ``pub.data['meas'].get_counts()`` eredményformát adja.
    """
    try:
        from qiskit_ibm_runtime.executor_sampler import Sampler
    except ImportError:  # régebbi qiskit-ibm-runtime
        from qiskit_ibm_runtime import SamplerV2 as Sampler
    return Sampler(mode=mode)


def first_counts(pub):
    """A publikáció első nem üres counts szótára + a data bin neve.

    Qiskit 2.x-ben a data bin kulcsa a regiszter neve (``'meas'``), nem az
    index — a korábbi ``pub.data[0]`` ``KeyError``-t dobott. Itt nem
    feltételezzük a nevet.

    Raises:
        RuntimeError: ha a publikációban nincs egyetlen nem üres bin sem.
    """
    for name in pub.data:
        try:
            counts = pub.data[name].get_counts()
        except Exception:
            continue
        if counts:
            return name, counts
    raise RuntimeError(f"üres data bin a jobban: {list(pub.data.keys())}")
