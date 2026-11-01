"""QDS — hardver elővizsgálat (KVÓTA NÉLKÜL).

Ez a szkript **nem** futtat QPU jobot, tehát nem fogyaszt IBM kvótát.
Csak a backend-listát, a qubit-adatokat és a kvótát állapítja meg.

Használat::

    python qds_preflight.py
"""

import argparse
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.join(_HERE, "src")
if os.path.isdir(_SRC) and _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from qds.constants import BACKEND_NAME, QUBIT, SIM_T2_US  # noqa: E402
from qds.ibm import CHANNEL, load_token  # noqa: E402


def connect(token=None):
    """Csatlakozás; modern csatornán, hiba esetén a legacy csatornával."""
    from qiskit_ibm_runtime import QiskitRuntimeService

    token = token or load_token()
    errors = []
    for channel in (CHANNEL, "ibm_quantum"):
        try:
            svc = QiskitRuntimeService(channel=channel, token=token)
            print(f"[OK] csatorna: {channel}")
            return svc
        except Exception as exc:
            errors.append(f"{channel}: {type(exc).__name__}: {exc}")
    print("[HIBA] egyik csatorna sem működik:")
    for err in errors:
        print("   -", err)
    return None


def main(argv=None):
    parser = argparse.ArgumentParser(description="QDS hardver elővizsgálat")
    parser.add_argument("--backend", default=os.environ.get("QDS_BACKEND",
                                                            BACKEND_NAME))
    parser.add_argument("--qubit", type=int,
                        default=int(os.environ.get("QDS_QUBIT", QUBIT)))
    args = parser.parse_args(argv)

    svc = connect()
    if svc is None:
        return 2
    print("=" * 68)

    # --- 1. Elérhető eszközök ---
    try:
        backends = list(svc.backends())
        print(f"Eszközök száma: {len(backends)}")
        for b in backends:
            try:
                status = (b.status_msg or "").strip()[:40]
                print(f"   - {b.name:<28} {b.num_qubits:>4} qubit  {status}")
            except Exception:
                print(f"   - {getattr(b, 'name', b)}")
    except Exception as exc:
        print("backend-lista hiba:", exc)

    # --- 2. A keresett backend ---
    name = None
    for cand in (args.backend, BACKEND_NAME, "ibm_fez", "ibm_marrakesh"):
        try:
            svc.backend(name=cand)
            name = cand
            break
        except Exception:
            continue
    if name is None:
        print(f"\n[HIBA] \"{args.backend}\" nem érhető el, és nincs tartalék sem.")
        print("       Válassz elérhető eszközt a fenti listából (--backend).")
        return 3

    backend = svc.backend(name=name)
    print("=" * 68)
    print(f"Backend: {name}  ({backend.num_qubits} qubit)")
    dt = getattr(backend, "dt", None)
    print(f"dt = {dt * 1e9:.4f} ns (nominális)" if dt else "dt = ismeretlen")

    # --- 3. A cél-qubit állapota ---
    try:
        st = backend.status()
        print(f"Állapot: {st.status_msg.strip()}  ({st.operational})")
    except Exception:
        pass

    qubit = args.qubit
    try:
        props = backend.qubit_properties(qubit)
        if props is None:
            print(f"Qubit {qubit}: NINCS tulajdonság (nem működő?)")
        else:
            print(f"Qubit {qubit}: f={props.frequency / 1e9:.4f} GHz  "
                  f"T1={props.t1 * 1e6:.1f} us  T2={props.t2 * 1e6:.1f} us")
            print(f"   a szimulátor T2-feltevése ({SIM_T2_US:.0f} us) a "
                  f"valósághoz képest {SIM_T2_US / (props.t2 * 1e6):.2f}×")
    except Exception as exc:
        print(f"Qubit {qubit} adata nem elérhető: {type(exc).__name__}: {exc}")

    # --- 4. Kvóta (ez még MINDIG szabad) ---
    print("-" * 68)
    for label, fn in (
        ("open plan (perc)", lambda: svc.remaining_job_minutes()),
        ("usage", lambda: svc.usage()),
        ("account", lambda: svc.my_account()),
    ):
        try:
            print(f"{label}: {fn()}")
        except Exception as exc:
            print(f"{label}: nem elérhető ({type(exc).__name__})")

    print("=" * 68)
    print("ELŐZETES: kvóta nem fogyott. Hardver job indításához: "
          "hahn_echo_t2_qam.py --mode hardware --dry-run, majd --mode hardware")
    return 0


if __name__ == "__main__":
    from qds.cli import run

    sys.exit(run(main))
