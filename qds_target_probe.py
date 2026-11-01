"""QDS — hardver elővizsgálat 2. (KVÓTA NÉLKÜL).

Cél: a valódi dt / granularity, a cél-qubit (alapból 91) életképessége, és ha
az rossz, a legjobb T2-es qubit kiválasztása.

**Nem** indít QPU jobot → nem fogyaszt kvótát.

Használat::

    python qds_target_probe.py [--qubit 91]
"""

import argparse
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.join(_HERE, "src")
if os.path.isdir(_SRC) and _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from qds.constants import BACKEND_NAME, QUBIT  # noqa: E402
from qds.ibm import get_backend  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description="QDS target-vizsgálat")
    parser.add_argument("--backend", default=os.environ.get("QDS_BACKEND",
                                                            BACKEND_NAME))
    parser.add_argument("--qubit", type=int,
                        default=int(os.environ.get("QDS_QUBIT", QUBIT)))
    args = parser.parse_args(argv)
    qubit = args.qubit

    backend = get_backend(args.backend)
    tgt = backend.target
    print("=" * 70)
    print(f"Backend: {args.backend}   num_qubits={backend.num_qubits}")

    # --- időzítés ---
    dt = getattr(backend, "dt", None)
    tdt = getattr(tgt, "dt", None)
    gran = getattr(tgt, "granularity", None)
    print(f"backend.dt            = {dt}")
    print(f"target.dt             = {tdt}")
    print(f"target.granularity    = {gran}")
    print(f"target.pulse_alignment= {getattr(tgt, 'pulse_alignment', None)}")
    eff_dt = tdt or dt
    if eff_dt:
        print(f"  → 1 dt = {eff_dt * 1e9:.4f} ns; a 10 us várakozás = "
              f"{10e-6 / eff_dt:.1f} dt")
        n800 = int(800e-6 / eff_dt)
        g = max(1, gran or 1)
        print(f"  → 800 us várakozás = {800e-6 / eff_dt:.1f} dt "
              f"(granularitásra igazítva: {n800 // g} × {g})")
    else:
        print("  → dt ISMERETLEN: a τ→dt konverzió nem biztonságos!")

    # --- a cél-qubit ---
    print("-" * 70)
    qprops = getattr(tgt, "qubit_properties", None)
    print(f"qubit_properties lista hossza: {len(qprops) if qprops else 0}")
    p = qprops[qubit] if qprops and qubit < len(qprops) else None
    print(f"Qubit {qubit} target.qubit_properties: {p}")
    try:
        print(f"Qubit {qubit} backend.qubit_properties: "
              f"{backend.qubit_properties(qubit)}")
    except Exception as exc:
        print(f"backend.qubit_properties({qubit}) hiba: {exc}")

    # --- működő qubitek ---
    print("-" * 70)
    good = []
    if qprops:
        for i, props in enumerate(qprops):
            if props is None:
                continue
            t1 = getattr(props, "t1", None)
            t2 = getattr(props, "t2", None)
            if t1 and t2:
                good.append((i, t1, t2, getattr(props, "frequency", None)))
    print(f"Valós (T1/T2-vel rendelkező) qubitek: {len(good)} / {len(qprops or [])}")
    if good:
        best = sorted(good, key=lambda x: -x[2])[:10]
        print("Legjobb 10 T2 szerint:")
        print("   qubit      T1(us)     T2(us)    freq(GHz)")
        for i, t1, t2, freq in best:
            fs = f"{freq / 1e9:8.4f}" if freq else "     n/a"
            mark = " <== CÉL" if i == qubit else ""
            print(f"   {i:>5}  {t1 * 1e6:8.1f}  {t2 * 1e6:9.1f}   {fs}{mark}")
        if any(g[0] == qubit for g in good):
            sel = next(g for g in good if g[0] == qubit)
            rank = sorted(good, key=lambda x: -x[2]).index(sel) + 1
            print(f"\n>>> A {qubit}. qubit működik, T2={sel[2] * 1e6:.1f} us, "
                  f"rangsor={rank}/{len(good)}")
        else:
            print(f"\n>>> A {qubit}. QUBIT NEM szerepel a működő listában!")
            print(f">>> Legjobb alternatíva: qubit {best[0][0]} "
                  f"(T2={best[0][2] * 1e6:.1f} us)")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    from qds.cli import run

    sys.exit(run(main))
