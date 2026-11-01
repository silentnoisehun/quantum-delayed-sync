"""Kapcsolat-teszt az IBM Quantumhoz — kvóta nélkül.

Csak bejelentkezik és kiolvassa a cél-qubit kalibrációját; **nem** küld jobot,
tehát nem fogyaszt kvótát. A tokent az ``IBM_TOKEN_PATH`` környezeti változó
vagy a repo gyökerében lévő ``ibm_token.json`` adja (lásd ``.gitignore``).

Korábbi verzió: a token útvonala be volt égetve (``D:\\codex\\...``), így a
szkript minden más gépen elszállt.

Használat::

    python test_connection.py [--backend ibm_kingston] [--qubit 91]
"""

import argparse
import os
import sys

_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
if os.path.isdir(_SRC) and _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from qds.ibm import get_backend, load_token  # noqa: E402 — a sys.path miatt


def main(argv=None):
    from qds.constants import BACKEND_NAME, QUBIT

    parser = argparse.ArgumentParser(description="IBM Quantum kapcsolat-teszt")
    parser.add_argument("--backend", default=BACKEND_NAME)
    parser.add_argument("--qubit", type=int, default=QUBIT)
    args = parser.parse_args(argv)

    try:
        token = load_token()
    except (FileNotFoundError, ValueError) as exc:
        print(f"TOKEN HIBA: {exc}", file=sys.stderr)
        return 2
    print(f"Token betöltve (len={len(token)})")

    try:
        backend = get_backend(args.backend, token=token)
    except Exception as exc:
        print(f"KAPCSOLAT HIBA: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 3

    print(f"Backend: {args.backend} ({backend.num_qubits} qubit)")
    try:
        props = backend.qubit_properties(args.qubit)
        print(f"Qubit {args.qubit}: T1={props.t1 * 1e6:.1f} us  "
              f"T2={props.t2 * 1e6:.1f} us")
    except Exception as exc:
        print(f"Qubit {args.qubit} adata nem elérhető: {exc}")
    print("OK — kvóta nem fogyott (nem küldtünk jobot).")
    return 0


if __name__ == "__main__":
    from qds.cli import run

    sys.exit(run(main))
