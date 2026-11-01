"""QDS — robusztusság-elemzés a MEGLÉVŐ adatokon (kvóta nélkül).

A `qds_multirun_stats.py` a görbére illesztett T₂_eff-et adja, de a hibasáv
csak a görbe-illesztés görbületéből jön (curve_fit kovariancia), ami
rendszerint alulbecsüli a valódi bizonytalanságot. Ez a szkript három
független ellenőrzést ad ugyanarra az adatra:

1. **Bootstrap (rezidualis)** — a pontokra visszatett maradékok újramintázása
   (case resampling), 2000 ismétlés → T₂_eff és T₁_eff percentilis hibasáv.
   Nem igényel új mérést: a meglévő 16 pontból dolgozik.
2. **Érzékenység a τ-tartományra** — T₂ illesztése levágott τ-rácsokra
   (teljes / ≤400 µs / ≤200 µs / ≥25 µs). Ha a hosszú τ-k uralják az
   eredményt, a rövid-tartományos illesztés eltér.
3. **Súlyozott illesztés** — minden pont shot-noise súlyával (1/σ², a
   binomiális varianciából). Ha a súlyozatlan és súlyozott illesztés
   egyezik, a pontok szórása összhangban van a statisztikai zajjal.

Kimenet: ``results/robustness.json`` + szöveges összegzés.

Használat::

    python qds_robustness.py            # a 5 futás összevont elemzése
    python qds_robustness.py --run 3    # csak a 3. futás
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
    TAUS_US,
    THETA,
)
from qds.data import load_runs, multirun_summary, p0_series  # noqa: E402
from qds.model import echo_model, fit_t1, fit_t2  # noqa: E402

RESULTS = os.path.join(_HERE, "results")
BOOTSTRAP_N = 2000
BOOTSTRAP_SEED = 12345


def shot_sigma_pct(p_pct, shots=1024):
    """A mért P(0)% binomiális szórása (százalékpontban)."""
    p = np.clip(np.asarray(p_pct, dtype=float) / 100.0, 1e-6, 1 - 1e-6)
    return np.sqrt(p * (1 - p) / shots) * 100


def bootstrap_fit(taus_us, values_pct, fitter, key, n=BOOTSTRAP_N,
                  seed=BOOTSTRAP_SEED):
    """Rezidualis bootstrap egy illesztő függvényre.

    Args:
        taus_us: τ értékek.
        values_pct: mért P(0)% értékek.
        fitter: ``fitter(taus, values) -> dict`` — **egyargumentumos** wrapperek
            (pl. ``lambda t, y: fit_t2(t, y, t1_us)``). Korábbi verzióban a
            nyers ``fit_t2``/``fit_t1`` kapott egy harmadik pozicionális
            argumentumot, ami a ``fit_t1``-nél a ``theta`` helyére csúszott —
            attól a T1-bootstrap értelmetlen értéket adott.
        key: melyik kulcs hordozza az illesztett időállandót (``t2_us``/``t1_us``).
        n: ismétlések száma.
        seed: RNG seed (reprodukálható).

    Returns:
        dict: ``median``, ``ci_low``, ``ci_high``, ``std`` (a fő paraméterre,
        µs-ban), ``n_ok`` (sikeres illesztések).
    """
    rng = np.random.default_rng(seed)
    t = np.asarray(taus_us, dtype=float)
    y = np.asarray(values_pct, dtype=float)
    base = fitter(t, y)
    if base[key] is None:
        return {"median": None, "ci_low": None, "ci_high": None,
                "std": None, "n_ok": 0}
    # a modell görbéje a rácsra, és a maradékok
    model_curve = np.asarray(base["curve_pct"], dtype=float)
    resid = y - model_curve
    draws = []
    for _ in range(n):
        y_star = model_curve + rng.choice(resid, size=resid.size, replace=True)
        out = fitter(t, y_star)
        if out[key] is not None and np.isfinite(out[key]):
            draws.append(out[key])
    if not draws:
        return {"median": None, "ci_low": None, "ci_high": None,
                "std": None, "n_ok": 0}
    arr = np.asarray(draws)
    return {
        "median": float(np.median(arr)),
        "ci_low": float(np.percentile(arr, 2.5)),
        "ci_high": float(np.percentile(arr, 97.5)),
        "std": float(np.std(arr, ddof=1)),
        "n_ok": int(arr.size),
    }


def weighted_fit(taus_us, values_pct, shots=1024, t1_us=T1_CALIBRATED_US):
    """Shot-noise súlyozott T2-illesztés (sigma = binomiális szórás).

    Visszaadja a T2_eff-et és a relatív eltérést a súlyozatlan illesztéshez.
    """
    from scipy.optimize import curve_fit

    t = np.asarray(taus_us, dtype=float)
    y = np.asarray(values_pct, dtype=float) / 100.0
    sigma = shot_sigma_pct(values_pct, shots) / 100.0
    mask = t > 0
    t2_unw = fit_t2(taus_us, values_pct, t1_us)["t2_us"]
    try:
        popt, pcov = curve_fit(
            lambda tt, t2: echo_model(tt, t2, t1_us * 1e-6),
            t[mask] * 1e-6, y[mask], p0=[150e-6], sigma=sigma[mask],
            absolute_sigma=True, bounds=([1e-8], [20e-3]),
        )
    except Exception:
        return {"t2_us": None, "stderr_us": None, "t2_unweighted_us": t2_unw,
                "rel_diff_pct": None}
    t2w = float(popt[0]) * 1e6
    return {
        "t2_us": t2w,
        "stderr_us": float(np.sqrt(pcov[0][0])) * 1e6
        if np.isfinite(pcov[0][0]) else None,
        "t2_unweighted_us": t2_unw,
        "rel_diff_pct": (100 * (t2w - t2_unw) / t2_unw) if t2_unw else None,
    }


def truncation_sweep(taus_us, echo_pct, t1_us=T1_CALIBRATED_US):
    """T2 illesztése több, eltérő hosszúságú τ-tartományra."""
    taus = np.asarray(taus_us, dtype=float)
    echo = np.asarray(echo_pct, dtype=float)
    subsets = {
        "full": taus <= 800,
        "up_to_400us": taus <= 400,
        "up_to_200us": taus <= 200,
        "from_25us": taus >= 25,
        "short_0_100us": taus <= 100,
    }
    out = {}
    for label, mask in subsets.items():
        if mask.sum() < 4:  # legalább 3 pozitív τ kell az illesztéshez
            out[label] = None
            continue
        fit = fit_t2(taus[mask], echo[mask], t1_us)
        out[label] = {
            "taus_us": [float(x) for x in taus[mask]],
            "t2_us": fit["t2_us"],
            "stderr_us": fit["stderr_us"],
            "rms_pct": fit["rms_pct"],
        }
    return out


def analyse_series(taus_us, echo_pct, ctrl_pct, shots=1024, t1_us=T1_CALIBRATED_US,
                   bootstrap_n=BOOTSTRAP_N):
    """Egy (átlagolt vagy futásonkénti) görbepár teljes robusztusság-elemzése."""
    echo_fit = fit_t2(taus_us, echo_pct, t1_us)
    ctrl_fit = fit_t1(taus_us, ctrl_pct)
    return {
        "t2_point_us": echo_fit["t2_us"],
        "t2_point_stderr_us": echo_fit["stderr_us"],
        "t2_bootstrap": bootstrap_fit(
            taus_us, echo_pct,
            lambda t, y: fit_t2(t, y, t1_us),
            key="t2_us", n=bootstrap_n),
        "t1_point_us": ctrl_fit["t1_us"],
        "t1_point_stderr_us": ctrl_fit["stderr_us"],
        "t1_bootstrap": bootstrap_fit(
            taus_us, ctrl_pct,
            lambda t, y: fit_t1(t, y, THETA),
            key="t1_us", n=bootstrap_n),
        "t2_weighted": weighted_fit(taus_us, echo_pct, shots, t1_us),
        "t2_truncation": truncation_sweep(taus_us, echo_pct, t1_us),
        "shots": shots,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="QDS robusztusság-elemzés")
    parser.add_argument("--results-dir", default=RESULTS)
    parser.add_argument("--run", type=int, default=None,
                        help="csak ez a futás (alapból: minden futás összevontan)")
    parser.add_argument("--bootstrap", type=int, default=BOOTSTRAP_N)
    args = parser.parse_args(argv)

    runs = load_runs(args.results_dir)
    if args.run is not None:
        runs = [r for r in runs if r.get("run") == args.run]
        if not runs:
            print(f"HIBA: nincs {args.run}. futás", file=sys.stderr)
            return 2
    summary = multirun_summary(runs, TAUS_US)
    t1_cal = summary["t1_calibrated_us"]
    t2_cal = summary["t2_calibrated_us"]
    shots = runs[0].get("shots", 1024)

    # Az összevont görbe: a futások átlaga (a legjobban megalapozott becslés)
    taus = np.asarray(TAUS_US, dtype=float)
    echo_mean = np.asarray(summary["echo_mean_pct"], dtype=float)
    ctrl_mean = np.asarray(summary["ctrl_mean_pct"], dtype=float)

    print("=" * 78)
    print(f"ROBUSZTUSSÁG — {len(runs)} futás "
          f"({', '.join(str(r.get('run')) for r in runs)}), {shots} shot/pont")
    print("=" * 78)
    pooled = analyse_series(taus, echo_mean, ctrl_mean, shots, t1_cal, args.bootstrap)
    _report("összevont átlag", pooled, t1_cal, t2_cal)

    per_run = {}
    for r in runs:
        res = analyse_series(taus, p0_series(r, "echo"), p0_series(r, "ctrl"),
                             shots, t1_cal, bootstrap_n=min(args.bootstrap, 1000))
        per_run[str(r.get("run"))] = res
        b = res["t2_bootstrap"]
        print(f"  run{r.get('run')}: T2 = {res['t2_point_us']:6.1f} µs "
              f"(±{res['t2_point_stderr_us']:4.1f} fit), bootstrap "
              f"{b['ci_low']:6.1f}–{b['ci_high']:6.1f} µs, "
              f"súlyozott {res['t2_weighted']['t2_us']:6.1f} µs")

    out = {
        "n_runs": len(runs),
        "shots": shots,
        "t1_calibrated_us": t1_cal,
        "t2_calibrated_us": t2_cal,
        "bootstrap_n": args.bootstrap,
        "bootstrap_seed": BOOTSTRAP_SEED,
        "pooled": pooled,
        "per_run": per_run,
    }
    os.makedirs(args.results_dir, exist_ok=True)
    path = os.path.join(args.results_dir, "robustness.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
        f.write("\n")
    print("=" * 78)
    print(f"mentve: {os.path.relpath(path, _HERE)}")
    return 0


def _report(label, res, t1_cal, t2_cal):
    b2, b1 = res["t2_bootstrap"], res["t1_bootstrap"]
    print(f"\n[{label}]")
    print(f"  T2 illesztés (pont)      : {res['t2_point_us']:.2f} ± "
          f"{res['t2_point_stderr_us']:.2f} µs "
          f"(kalibrált {t2_cal:.1f}, arány {res['t2_point_us'] / t2_cal:.3f})")
    if b2["median"]:
        print(f"  T2 bootstrap (95%)       : {b2['median']:.2f} µs, "
              f"CI {b2['ci_low']:.2f}–{b2['ci_high']:.2f} µs "
              f"(std {b2['std']:.2f}, {b2['n_ok']} illesztés)")
        wider = b2["std"] / res["t2_point_stderr_us"]
        print(f"  bootstrap/fit hibaarány  : {wider:.2f}× "
              f"({'szélesebb' if wider > 1.2 else 'összhangban'})")
    w = res["t2_weighted"]
    if w["t2_us"]:
        print(f"  T2 súlyozott illesztés   : {w['t2_us']:.2f} ± "
              f"{w['stderr_us']:.2f} µs → eltérés a súlyozatlantól "
              f"{w['rel_diff_pct']:+.1f}%")
    print("  T2 érzékenység a τ-tartományra:")
    for key, val in res["t2_truncation"].items():
        if val:
            print(f"    {key:<15} ({len(val['taus_us'])} pont): "
                  f"{val['t2_us']:7.2f} ± {val['stderr_us']:5.2f} µs "
                  f"(RMS {val['rms_pct']:.2f}%)")
    print(f"  T1 illesztés (pont)      : {res['t1_point_us']:.2f} ± "
          f"{res['t1_point_stderr_us']:.2f} µs "
          f"(kalibrált {t1_cal:.1f}, arány "
          f"{res['t1_point_us'] / t1_cal:.3f})")
    if b1["median"]:
        print(f"  T1 bootstrap (95%)       : {b1['median']:.2f} µs, "
              f"CI {b1['ci_low']:.2f}–{b1['ci_high']:.2f} µs")


if __name__ == "__main__":
    from qds.cli import run

    sys.exit(run(main))
