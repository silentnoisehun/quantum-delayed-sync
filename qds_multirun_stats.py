"""QDS — több futás statisztikája (bírálói szint).

Egy futásból nincs T2-hibasáv: egyetlen pont 1024 shotból ~1 %. Az N futás
átlagának szórása viszont a tényleges időbeli ingadozást méri — és pont ez a
drift az, amit az echo kar integrál.

Kimenet: ``results/multirun_stats.json`` + szöveges összegzés a stdout-on.
A megengedhető következtetések határai: ``docs/QDS_REFEREE_STATS.md``.

A futásonkénti illesztés a :mod:`qds.model` közös modelljeit használja (a
kalibrált T1 a futásrekordból jön, nem konstansból).
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

from qds.constants import TAUS_US  # noqa: E402
from qds.data import load_runs, multirun_summary  # noqa: E402

RESULTS_DIR = os.path.join(_HERE, "results")


def main(argv=None):
    parser = argparse.ArgumentParser(description="QDS több futás statisztikája")
    parser.add_argument("--results-dir", default=RESULTS_DIR)
    args = parser.parse_args(argv)

    try:
        runs = load_runs(args.results_dir)
    except FileNotFoundError as exc:
        print(f"HIBA: {exc}", file=sys.stderr)
        return 2
    print(f"{len(runs)} futás található")
    summary = multirun_summary(runs, TAUS_US)
    t1_cal = summary["t1_calibrated_us"]
    t2_cal = summary["t2_calibrated_us"]
    print(f"kalibrált: T1={t1_cal:.1f} us  T2={t2_cal:.1f} us")
    print("=" * 92)

    for arm, label in (("echo", "ECHO kar"), ("ctrl", "KONTROLL kar")):
        key = "echo_p0_per_run" if arm == "echo" else "ctrl_p0_per_run"
        table = summary[key]
        print(f"{label} — P(0)% futásonként, átlag ± szórás")
        print(" tau(us) | " + " | ".join(f"run{r.get('run', '?')}" for r in runs)
              + " |   átlag ± szór")
        print("-" * 92)
        for tau in TAUS_US:
            vals = table[str(tau)]
            m = float(np.nanmean(vals))
            s = float(np.nanstd(vals, ddof=1)) if len(vals) > 1 else 0.0
            cells = " | ".join(f"{v:6.2f}" for v in vals)
            print(f" {tau:>7} | {cells} | {m:8.2f} ± {s:4.2f}")
        print("-" * 92)

    print("=" * 92)
    print("FUTÁSONKÉNTI ILLESZTETT IDŐÁLLANDÓ")
    print(" run | job_id                 | T2_eff(us)   | T1_eff(us)   | "
          "T2/T2kal | T1/T1kal")
    print("-" * 92)
    for r in summary["per_run"]:
        t2 = r["t2_eff_us"]
        t1 = r["t1_eff_us"]
        t2s = f"{t2:7.1f} ±{r['t2_stderr_us']:4.1f}" if t2 else "       n/a     "
        t1s = f"{t1:7.1f} ±{r['t1_stderr_us']:4.1f}" if t1 else "       n/a     "
        r2 = f"{r['t2_ratio']:8.3f}" if r["t2_ratio"] else "     n/a"
        r1 = f"{r['t1_ratio']:8.3f}" if r["t1_ratio"] else "     n/a"
        print(f" {r['run']:>3} | {r['job_id']!s:<22} | {t2s} | {t1s} | "
              f"{r2} | {r1}")

    if summary["t2_eff_mean_us"]:
        m2 = summary["t2_eff_mean_us"]
        sd2 = summary["t2_eff_std_us"]
        sem = summary["t2_eff_sem_us"]
        print("-" * 92)
        print(f"T2_eff  átlag = {m2:.1f} ± {sd2:.1f} us (szórás, "
              f"N={summary['n_runs']}), felépő = ± {sem:.1f} us")
        print(f"        kalibrált T2 = {t2_cal:.1f} us → arány = "
              f"{m2 / t2_cal:.3f} ± {sem / t2_cal:.3f}")
        print(f"        az átlag a kalibráltnál KISEBB: {m2 / t2_cal:.2f}×")
    if summary["t1_eff_mean_us"]:
        m1 = summary["t1_eff_mean_us"]
        print(f"T1_eff  átlag = {m1:.1f} ± {summary['t1_eff_std_us']:.1f} us "
              f"(N={summary['n_runs']}), arány = {m1 / t1_cal:.3f}")

    print("=" * 92)
    print("MONOTONIA — minden futásban ellenőrizve")
    for arm, label in (("echo", "echo"), ("ctrl", "kontroll")):
        ok = summary["monotonia_runs_ok"][arm]
        print(f"  {label:<9}: {ok}/{summary['n_runs']} futás monoton")

    out = os.path.join(args.results_dir, "multirun_stats.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
        f.write("\n")
    print(f"mentve: {os.path.relpath(out, _HERE)}")
    return 0


if __name__ == "__main__":
    from qds.cli import run

    sys.exit(run(main))
