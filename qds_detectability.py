"""QDS — kimutatható-e a drift a mérési zajhoz képest? (chi²-teszt)

A kérdés: a futásonkénti T2_eff szórás valódi fizikai ingadozás, vagy csak a
shot noise terjedése?

Teszt: ha a futások közötti eltérés csak statisztikai zaj lenne, akkor a
futásonkénti szórás ≈ a futásonkénti illesztési hiba. A chi²-teszt:

    chi² = Σ (x_i − átlag)² / σ_i²        σ_i = a futás illesztési hibája

``df = N − 1`` mellett a chi² várható értéke ``df``; ennél jóval nagyobb érték
esetén az ingadozás nem magyarázható a számított zajjal (p < 0,01).

A szkript **a nyers adatokból** számol (``results/raw_counts_all_runs.json``),
nem beégetett számokból — a korábbi verzióban a T2/T1 értékek kézzel voltak
beírva, így az újabb futások nem kerültek bele.
"""

import argparse
import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.join(_HERE, "src")
if os.path.isdir(_SRC) and _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from qds.constants import TAUS_US  # noqa: E402
from qds.data import heterogeneity_chi2, load_runs, multirun_summary  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description="QDS drift-kimutathatóság (chi²)")
    parser.add_argument("--results-dir", default=os.path.join(_HERE, "results"))
    args = parser.parse_args(argv)

    try:
        runs = load_runs(args.results_dir)
    except FileNotFoundError as exc:
        print(f"HIBA: {exc}", file=sys.stderr)
        return 2
    summary = multirun_summary(runs, TAUS_US)
    per = [r for r in summary["per_run"] if r["t2_eff_us"]]
    if len(per) < 2:
        print("HIBA: legalább 2 sikeres illesztés kell a teszthez.", file=sys.stderr)
        return 2

    t2 = np.array([r["t2_eff_us"] for r in per])
    t2_se = np.array([r["t2_stderr_us"] for r in per])
    t1 = np.array([r["t1_eff_us"] or np.nan for r in per])
    t1_se = np.array([r["t1_stderr_us"] or np.nan for r in per])
    ok1 = np.isfinite(t1)

    print("=" * 72)
    print(f"A {len(t2)} FUTÁS T2_eff (echo kar)")
    for r in per:
        print(f"  run{r['run']}: {r['t2_eff_us']:6.1f} ± {r['t2_stderr_us']:4.1f} us")

    d2 = heterogeneity_chi2(t2, t2_se)
    print(f"  átlag  : {d2['mean']:.1f} us   szórás {d2['sd']:.1f} us   "
          f"SEM {d2['sem']:.1f} us")
    print()
    print(f"Ha csak shot noise lenne, a futásonkénti szórás ≈ {d2['avg_stderr']:.1f} us")
    print(f"A MÉRT futásonkénti szórás                      = {d2['sd']:.1f} us")
    print(f"  → arány = {d2['sd'] / d2['avg_stderr']:.2f}×")
    print()
    print(f"chi² = {d2['chi2']:.1f}   df = {d2['dof']}   (nulla átlag = {d2['dof']})")
    print(f"p(nulla) = {d2['p_value']:.3e}   → {d2['verdict']}")
    print()

    if ok1.sum() >= 2:
        print("=" * 72)
        print("T1 KONTROLL-KAR — ugyanaz a teszt (a relaxáció stabil-e?)")
        for r in per:
            if r["t1_eff_us"]:
                print(f"  run{r['run']}: {r['t1_eff_us']:6.1f} ± "
                      f"{r['t1_stderr_us']:4.1f} us")
        d1 = heterogeneity_chi2(t1[ok1], t1_se[ok1])
        print(f"  átlag: {d1['mean']:.1f} us   szórás: {d1['sd']:.1f} us")
        print(f"  chi² = {d1['chi2']:.2f}   df = {d1['dof']}   "
              f"(nulla átlag = {d1['dof']})")
        print(f"  p(nulla) = {d1['p_value']:.3e}   → {d1['verdict']}")
        print()
        print(f"  T1: chi²={d1['chi2']:.2f}, p={d1['p_value']:.3e}")
        print(f"  T2: chi²={d2['chi2']:.2f}, p={d2['p_value']:.3e}")
        if d2["p_value"] < 0.01 <= d1["p_value"]:
            print("  → A drift a T2 (fázis-koherencia) szinten jelentkezik, "
                  "a T1-en (relaxáció) nem.")
        else:
            print("  → A két kar viselkedése nem válik szét egyértelműen; "
                  "lásd a korlátozásokat a docs/QDS_REFEREE_STATS.md-ban.")
    return 0


if __name__ == "__main__":
    from qds.cli import run

    sys.exit(run(main))
