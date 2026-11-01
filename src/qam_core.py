"""QAM integrátor — vékony kompatibilitási réteg a QDS közös magja fölött.

Korábban ez a modul közvetlenül a már nem létező ``qiskit_ibm_provider``-re
épült, és saját token-feloldást tartalmazott (eltérő sorrenddel, mint a
többi szkript). Most a :mod:`qds.ibm` modult használja, így a token-feloldás
és a csatorna-beállítás mindenhol ugyanaz.

Használat::

    from qam_core import QAM
    qam = QAM(backend="ibm_kingston", qubit=91)
    backend = qam.backend
"""

import sys

from qds.ibm import get_backend, load_token


class QAM:
    """IBM Quantum integrátor (a `quantum-sync` és más QAM projektekhez).

    Attributes:
        backend: aktív IBM backend objektum
        backend_name: a backend neve (pl. ``ibm_kingston``)
        qubit: a kalibrált cél-qubit sorszáma
        token: a feloldott API-kulcs (soha ne írd ki / ne commitold!)
    """

    def __init__(self, token=None, backend="ibm_kingston", qubit=91):
        self.backend_name = backend
        self.qubit = qubit
        self.token = token or load_token()
        print(f"Token betöltve (len={len(self.token)})")
        self.backend = get_backend(backend, token=self.token)

        try:
            props = self.backend.qubit_properties(self.qubit)
            if props and props.t1 and props.t2:
                print(f"  Qubit {self.qubit}: T1={props.t1 * 1e6:.1f} us  "
                      f"T2={props.t2 * 1e6:.1f} us")
        except Exception as exc:
            print(f"  qubit_properties nem elérhető: {exc}")


def main(argv=None):
    from qds.constants import BACKEND_NAME, QUBIT

    argv = sys.argv[1:] if argv is None else argv
    backend = argv[0] if argv else BACKEND_NAME
    qubit = int(argv[1]) if len(argv) > 1 else QUBIT
    qam = QAM(backend=backend, qubit=qubit)
    print(f"Backend: {qam.backend_name} ({qam.backend.num_qubits} qubit)")
    return 0


if __name__ == "__main__":
    from qds.cli import run

    sys.exit(run(main))
