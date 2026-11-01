"""QDS — a hardveres U→delay→U† sweep kiértékelése (kvóta nélkül).

Bemenet: ``results/qam_echo_<JOB_ID>.json`` (a job ID-ból visszakeresett,
beküldési sorrendű sorok). Kimenet: ``results/qam_echo_t2_results.json``.

A két kar két külön kérdésre válaszol:

* **kontroll kar** (csak T1-től függ) → a τ-tengely referenduma;
* **echo kar** → az echo-korlátozott T2 (ezt a mérés vizsgálja).

A korábbi verzió a **T2**-arányból mondta ki, hogy „ELTÖRÉS — a platform dt-je
nem a QPU valódi időzítése”, miközben a krónika ugyanarra az adatra a kontroll
karból „RENDBEN”-t kapott. A τ-tengely ítélete most egységesen a kontroll
karból jön (lásd :func:`qds.model.axis_verdict`).
"""

import argparse
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.join(_HERE, "src")
if os.path.isdir(_SRC) and _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from qds.constants import (  # noqa: E402
    BACKEND_NAME,
    CTRL_P0_AT_ZERO_PCT,
    QUBIT,
    SHOTS,
    T1_CALIBRATED_US,
    T2_CALIBRATED_US,
    TAUS_US,
    THETA,
)
from qds.model import (  # noqa: E402
    analytic,
    axis_verdict,
    fit_t1,
    fit_t2,
    ratio_difference,
    wilson_interval,
)

DEFAULT_JOB_ID = "dba0q2gc77vs738252kg"


def evaluate(job_id=DEFAULT_JOB_ID, results_dir=None, verbose=True):
    """Kiértékeli egy visszakeresett job adatait.

    Returns:
        dict: a ``qam_echo_t2_results.json`` tartalma.
    """
    results_dir = results_dir or os.path.join(_HERE, "results")
    path = os.path.join(results_dir, f"qam_echo_{job_id}.json")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    rows = data["rows"]
    if len(rows) != 2 * len(TAUS_US):
        raise ValueError(
            f"a sorok száma {len(rows)}, a beküldés szerint {2 * len(TAUS_US)} "
            f"kellene ({len(TAUS_US)} τ × 2 kar)")

    theta = THETA
    t1_cal = data.get("t1_calibrated_us") or T1_CALIBRATED_US
    t2_cal = data.get("t2_calibrated_us") or T2_CALIBRATED_US

    echo = {TAUS_US[i]: rows[2 * i]["p0"] for i in range(len(TAUS_US))}
    ctrl = {TAUS_US[i]: rows[2 * i + 1]["p0"] for i in range(len(TAUS_US))}
    shots = data.get("shots", SHOTS)

    if verbose:
        print(f"Job: {job_id}   backend={data.get('backend')}   "
              f"qubit={data.get('qubit')}")
        print("=" * 78)
        print(" tau(us) | echo MÉRT | echo MODELL | különb. | ctrl MÉRT | "
              "ctrl MODELL | különb.")
        print("-" * 78)
    exp_e, exp_c = {}, {}
    for tau in TAUS_US:
        pe, pc = analytic(tau, t1_cal, t2_cal, theta)
        pe, pc = float(pe), float(pc)
        exp_e[tau], exp_c[tau] = pe, pc
        if verbose:
            print(f" {tau:>7} | {echo[tau]:>9.2f} | {pe:>11.2f} | "
                  f"{echo[tau] - pe:>+8.2f} | {ctrl[tau]:>9.2f} | "
                  f"{pc:>11.2f} | {ctrl[tau] - pc:>+8.2f}")

    t2_fit = fit_t2(TAUS_US, [echo[t] for t in TAUS_US], t1_cal, theta)
    t1_fit = fit_t1(TAUS_US, [ctrl[t] for t in TAUS_US], theta)
    if not t2_fit["t2_us"] or not t1_fit["t1_us"]:
        raise ValueError("az illesztés nem sikerült (scipy hiba vagy kevés pont)")

    r2 = t2_fit["t2_us"] / t2_cal
    r2_err = t2_fit["stderr_us"] / t2_cal
    r1 = t1_fit["t1_us"] / t1_cal
    r1_err = t1_fit["stderr_us"] / t1_cal
    verdict = axis_verdict(r1, r1_err)
    ratio = ratio_difference(r1, r1_err, r2, r2_err)

    if verbose:
        print("=" * 78)
        print(f"Kalibrált: T1 = {t1_cal:.2f} us, T2 = {t2_cal:.2f} us")
        print(f"Illesztett T1 (kontroll): {t1_fit['t1_us']:.2f} ± "
              f"{t1_fit['stderr_us']:.2f} us  (arány {r1:.3f} ± {r1_err:.3f}, "
              f"RMS {t1_fit['rms_pct']:.2f} %)")
        print(f"Illesztett T2 (echo)    : {t2_fit['t2_us']:.2f} ± "
              f"{t2_fit['stderr_us']:.2f} us  (arány {r2:.3f} ± {r2_err:.3f}, "
              f"RMS {t2_fit['rms_pct']:.2f} %)")
        print(f"τ-TENGELY: {verdict['text']}")
        print(f"ARÁNY-KÜLÖNBSÉG: {ratio['difference']:+.3f} = "
              f"{ratio['n_sigma']:.1f}σ → "
              + ("azonos időskála (hiba)" if ratio["same_timescale"]
                 else "nem időskálázó hiba, valódi extra dekoherencia"))
        print("-" * 78)
        _print_conditions(echo, ctrl, shots)

    out = {
        "job_id": job_id,
        "backend": data.get("backend", BACKEND_NAME),
        "qubit": data.get("qubit", QUBIT),
        "theta": theta,
        "shots": shots,
        "t1_calibrated_us": t1_cal,
        "t2_calibrated_us": t2_cal,
        "t2_fitted_us": t2_fit["t2_us"],
        "t2_fitted_stderr_us": t2_fit["stderr_us"],
        "t1_fitted_us": t1_fit["t1_us"],
        "t1_fitted_stderr_us": t1_fit["stderr_us"],
        "tau_axis_ratio_t1": r1,
        "tau_axis_ratio_t1_stderr": r1_err,
        "t2_ratio": r2,
        "t2_ratio_stderr": r2_err,
        # Visszafelé kompatibilitás: a korábbi kulcs a T2-arányt jelentette
        # (a T2/T2_kalibrált hányadost), NEM a τ-tengelyét — lásd a
        # tau_axis_ratio_t1 / tau_axis_ok mezőket.
        "tau_axis_ratio": r2,
        "tau_axis_ok": verdict["axis_ok"],
        "tau_axis_verdict": verdict["text"],
        "ratio_difference": ratio["difference"],
        "ratio_difference_n_sigma": ratio["n_sigma"],
        "fit_rms_pct": t2_fit["rms_pct"],
        "tau_us": list(TAUS_US),
        "echo_measured_pct": [echo[t] for t in TAUS_US],
        "echo_model_pct": [exp_e[t] for t in TAUS_US],
        "ctrl_measured_pct": [ctrl[t] for t in TAUS_US],
        "ctrl_model_pct": [exp_c[t] for t in TAUS_US],
        "echo_wilson95_pct": [list(wilson_interval(echo[t], shots)) for t in TAUS_US],
        "raw_counts": [r["counts"] for r in rows],
    }
    return out


def _print_conditions(echo, ctrl, shots):
    mono_e = all(echo[TAUS_US[i]] > echo[TAUS_US[i + 1]]
                 for i in range(len(TAUS_US) - 1))
    mono_c = all(ctrl[TAUS_US[i]] < ctrl[TAUS_US[i + 1]]
                 for i in range(len(TAUS_US) - 1))
    lo0, hi0 = wilson_interval(echo[0], shots)
    print("Érvényes mérésfeltételek:")
    print(f"  1. Kontroll monoton nő   : {'IGEN' if mono_c else 'NEM'}")
    print(f"  2. Echo monoton csökken  : {'IGEN' if mono_e else 'NEM'}")
    print(f"  3. τ=0 echo ≈ 100%       : {'IGEN' if echo[0] > 98 else 'NEM'} "
          f"({echo[0]:.2f}%, Wilson95 {lo0:.2f}–{hi0:.2f})")
    print(f"  4. τ=0 kontroll ≈ {CTRL_P0_AT_ZERO_PCT:.2f}% : "
          f"{'IGEN' if abs(ctrl[0] - CTRL_P0_AT_ZERO_PCT) < 1.5 else 'NEM'} "
          f"({ctrl[0]:.2f}%)")


def main(argv=None):
    parser = argparse.ArgumentParser(description="QDS eredmény-kiértékelés")
    parser.add_argument("job_id", nargs="?", default=DEFAULT_JOB_ID)
    parser.add_argument("--results-dir", default=None)
    args = parser.parse_args(argv)

    out = evaluate(args.job_id, args.results_dir)
    results_dir = args.results_dir or os.path.join(_HERE, "results")
    path = os.path.join(results_dir, "qam_echo_t2_results.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
        f.write("\n")
    print(f"Mentve: {os.path.relpath(path, _HERE)}")
    return 0


if __name__ == "__main__":
    from qds.cli import run

    sys.exit(run(main))
