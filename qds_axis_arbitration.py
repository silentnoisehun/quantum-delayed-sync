"""QDS — a kontroll kar T1-illesztése: a τ-tengely döntőbírája.

A két kar eltérően sérül a modelltől:

* **echo** gyorsabban hanylik, mint a kalibrált T2 mondja;
* **kontroll** a kalibrált T1-gyel konzisztensen hanylik.

Ha a hiba **időzítési** (a QPU a beadott dt-t más arányban számolta), akkor a
két illesztett érték **azonos arányban** tolódna el (T1_eff/T1 ≈ T2_eff/T2).

Ha viszont T1 illeszkedik és a T2 nem, akkor az **nem időskálázó hiba**,
hanem valódi extra dekoherencia az echo karban (frekvencia-drift stb.).

A szkript a job ID-t argumentumból (vagy ``QDS_JOB_ID`` környezeti
változóból) veszi — korábban be volt égetve, ezért más futásra nem működött.
"""

import argparse
import json
import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.join(_HERE, "src")
if os.path.isdir(_SRC) and _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from qds.constants import (  # noqa: E402
    T1_CALIBRATED_US,
    T2_CALIBRATED_US,
    TAUS_US,
    THETA,
)
from qds.model import ctrl_model, fit_t1, fit_t2, ratio_difference  # noqa: E402

DEFAULT_JOB_ID = "dba0q2gc77vs738252kg"


def main(argv=None):
    parser = argparse.ArgumentParser(description="QDS kontroll-kar arbitráció")
    parser.add_argument("job_id", nargs="?",
                        default=os.environ.get("QDS_JOB_ID", DEFAULT_JOB_ID))
    parser.add_argument("--results-dir",
                        default=os.path.join(_HERE, "results"))
    args = parser.parse_args(argv)

    path = os.path.join(args.results_dir, f"qam_echo_{args.job_id}.json")
    with open(path, encoding="utf-8") as f:
        rows = json.load(f)["rows"]
    n = len(TAUS_US)
    if len(rows) != 2 * n:
        raise ValueError(f"{len(rows)} sor van, {2 * n} kellene")
    echo = np.array([rows[2 * i]["p0"] for i in range(n)]) / 100
    ctrl = np.array([rows[2 * i + 1]["p0"] for i in range(n)]) / 100
    t = np.array(TAUS_US, dtype=float) * 1e-6

    t1_cal = T1_CALIBRATED_US
    t2_cal = T2_CALIBRATED_US

    print("=" * 74)
    print("A) KONTROLL kar → T1 illesztése (a τ-tengely bírája)")
    f1 = fit_t1(TAUS_US, ctrl * 100, THETA)
    print(f"   T1_ill = {f1['t1_us']:7.2f} ± {f1['stderr_us']:.2f} us   "
          f"(offset {f1['offset_pct']:+.2f} %, RMS {f1['rms_pct']:.2f} %)")
    r1 = f1["t1_us"] / t1_cal
    r1_err = f1["stderr_us"] / t1_cal
    print(f"   T1_ill / T1_kalibrált = {r1:.3f} ± {r1_err:.3f}")

    print("=" * 74)
    print("B) ECHO kar → T2 illesztése (T1 rögzítve a kalibrált értéken)")
    f2 = fit_t2(TAUS_US, echo * 100, t1_cal, THETA)
    print(f"   T2_ill = {f2['t2_us']:7.2f} ± {f2['stderr_us']:.2f} us   "
          f"(RMS {f2['rms_pct']:.2f} %)")
    r2 = f2["t2_us"] / t2_cal
    r2_err = f2["stderr_us"] / t2_cal
    print(f"   T2_ill / T2_kalibrált = {r2:.3f} ± {r2_err:.3f}")

    print("=" * 74)
    print("C) A két kar UGYANAZT az arányt adja? (időskála-teszt)")
    d = ratio_difference(r1, r1_err, r2, r2_err)
    print(f"   T1 arány = {r1:.3f}      T2 arány = {r2:.3f}")
    print(f"   különbség = {d['difference']:+.3f} = {d['n_sigma']:.1f}σ")
    if d["same_timescale"]:
        print("   → AZONOS eltolódás: rejtett időskála-hiba gyanúja nyer.")
    else:
        print("   → NEM időskálázó hiba: valódi extra dekoherencia az echo karban.")

    print("=" * 74)
    print("D) A kontroll-modell részletei (kalibrált vs. illesztett T1)")
    print("   tau(us)    mért   modell(T1=kalibrált)   modell(T1=illesztett)")
    for i, tau in enumerate(TAUS_US):
        mc = ctrl_model(t[i:i + 1], t1_cal * 1e-6)[0] * 100
        mf = f1["curve_pct"][i]
        print(f"   {tau:>6}   {ctrl[i] * 100:6.2f}   {mc:>17.2f}   {mf:>19.2f}")
    return 0


if __name__ == "__main__":
    from qds.cli import run

    sys.exit(run(main))
