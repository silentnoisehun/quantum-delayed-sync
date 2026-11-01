"""QDS — helyi környezet-ellenőrzés (kvóta nélkül, IBM nélkül is fut).

Ellenőrzi a verziókat, a `delay`→dt konverziót és a Qiskit 2.x
kompatibilitást. Ha van token, a valódi backend targetjét is lekérdezi;
ha nincs, a ``FakeKingston`` (a valódi Heron r2 target snapshotja) alapján
ellenőriz — így a szkript token nélkül is hasznos.

Használat::

    python qds_env_check.py [--offline]
"""

import argparse
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.join(_HERE, "src")
if os.path.isdir(_SRC) and _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from qds.constants import BACKEND_NAME, QUBIT, TAUS_US  # noqa: E402


def _versions():
    import qiskit
    print("qiskit", qiskit.__version__)
    for mod in ("qiskit_aer", "qiskit_ibm_runtime"):
        try:
            m = __import__(mod)
            print(mod, getattr(m, "__version__", "?"))
        except ImportError:
            print(mod, "NINCS TELEPÍTVE")


def _backend(offline):
    """A valódi backend, vagy offline módban a beépített fake target."""
    from qiskit_ibm_runtime.fake_provider import FakeKingston

    if offline:
        print("OFFLINE mód: FakeKingston target használva (nem valódi backend)")
        return FakeKingston(), "FakeKingston (Heron r2 snapshot)"

    try:
        from qds.ibm import get_backend
        return get_backend(BACKEND_NAME), BACKEND_NAME
    except (FileNotFoundError, ValueError) as exc:
        print(f"Nincs használható token ({exc.__class__.__name__}) → offline mód")
        return FakeKingston(), "FakeKingston (Heron r2 snapshot)"


def main(argv=None):
    parser = argparse.ArgumentParser(description="QDS környezet-ellenőrzés")
    parser.add_argument("--offline", action="store_true",
                        help="token nélkül, a FakeKingston targettel")
    args = parser.parse_args(argv)

    _versions()
    backend, name = _backend(args.offline)
    tgt = backend.target
    print(f"backend: {name}  ({backend.num_qubits} qubit)")
    print(f"target.dt = {tgt.dt}  | granularity = {tgt.granularity}  | "
          f"pulse_alignment = {tgt.pulse_alignment}")

    # --- delay → dt konverzió a target alapján ---
    from qiskit import QuantumCircuit, transpile

    print("delay konverzió (a transzpiler a cél dt-jével számol):")
    for tau in (1, 10, 800):
        qc = QuantumCircuit(1)
        qc.x(0)
        qc.delay(tau, 0, unit="us")
        qc.measure_all()
        tqc = transpile(qc, backend, optimization_level=0, initial_layout=[QUBIT])
        for inst in tqc.data:
            if inst.operation.name == "delay":
                physical = inst.operation.duration * tgt.dt * 1e6
                print(f"  tau={tau:>4} us → {inst.operation.duration} "
                      f"{inst.operation.unit}  (= {physical:.2f} us "
                      f"dt={tgt.dt * 1e9:.1f} ns mellett)")

    # --- a τ-rács durációi a target dt-jével ---
    print(f"A τ-rács ({', '.join(str(t) for t in TAUS_US)} us) "
          f"a {tgt.dt * 1e9:.2f} ns dt-vel:")
    for tau in TAUS_US:
        print(f"  {tau:>4} us → {round(tau * 1e-6 / tgt.dt):>9} dt")

    # --- Qiskit 2.x API ---
    qc2 = QuantumCircuit(1)
    try:
        qc2.u(0.3, 0.4, 0.5, 0)
        gate = qc2.data[0].operation
        print("qc.u OK →", gate.name, "| inverse() →", gate.inverse().name)
    except Exception as exc:
        print("qc.u hiba:", type(exc).__name__, exc)
    return 0


if __name__ == "__main__":
    from qds.cli import run

    sys.exit(run(main))
