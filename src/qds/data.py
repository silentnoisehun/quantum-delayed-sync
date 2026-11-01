"""Nyers adatbeolvasás és a több futás statisztikája.

Kanonikus nyers forma: ``results/result_run{N}_kingston_1024.json`` (egy futás),
illetve a ``results/raw_counts_all_runs.json`` (minden futás egy fájlban,
fájlnév-kulcsokkal). A részletes séma: ``docs/qds_raw_schema.md``.
"""

import glob
import json
import os
import re

import numpy as np

from qds.constants import TAUS_US


def default_results_dir():
    """A repository ``results/`` könyvtára (a hívó fájljától függetlenül)."""
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(here, "..", "..", "results"))


def load_runs(results_dir=None):
    """Visszaadja a futásokat növekvő ``run`` sorrendben.

    Elsődlegesen a ``raw_counts_all_runs.json``-t olvassa; ha az nincs,
    a ``result_run*.json`` fájlokra esik vissza. Minden visszaadott rekord
    legalább ezeket tartalmazza: ``run``, ``job_id``, ``points``, ahol a
    pontok ``{'tau_us', 'arm', 'counts', 'p0_pct'}`` szótárak.

    Raises:
        FileNotFoundError: ha egyáltalán nincs adat a könyvtárban.
    """
    results_dir = results_dir or default_results_dir()
    merged_path = os.path.join(results_dir, "raw_counts_all_runs.json")
    runs = []
    if os.path.exists(merged_path):
        with open(merged_path, encoding="utf-8") as f:
            merged = json.load(f)
        runs = [merged[k] for k in sorted(merged, key=_run_number)]
    else:
        for fn in sorted(glob.glob(os.path.join(results_dir, "result_run*.json")),
                         key=_run_number):
            with open(fn, encoding="utf-8") as f:
                runs.append(json.load(f))
    if not runs:
        raise FileNotFoundError(f"nincs nyers futásadat itt: {results_dir}")
    return runs


def _run_number(name):
    m = re.search(r"run(\d+)", os.path.basename(name))
    return int(m.group(1)) if m else 10**6


def p0_series(run, arm, taus_us=TAUS_US):
    """Egy futás adott karának P(0)% értékei a τ-rács sorrendjében.

    Hiányzó pont helyére ``nan`` kerül (a statisztikák NaN-tudatosak).
    """
    out = []
    for tau in taus_us:
        val = next(
            (p["p0_pct"] for p in run["points"]
             if p.get("arm") == arm and p.get("tau_us") == tau),
            np.nan,
        )
        out.append(float(val))
    return np.asarray(out, dtype=float)


def series_table(runs, arm, taus_us=TAUS_US):
    """``{tau_us: [érték futásonként]}`` + átlag/szórás a τ-rácson."""
    table = {tau: [p0_series(r, arm, taus_us)[i] for r in runs]
             for i, tau in enumerate(taus_us)}
    return table


def multirun_summary(runs, taus_us=TAUS_US):
    """A több futás összesített statisztikája (a ``multirun_stats.json`` tartalma).

    A futásonkénti T2/T1 illesztés a :mod:`qds.model` modelljeit használja.
    A kalibrált T1/T2 a futásrekordokból jön (mérés közbeni érték), és csak
    akkor esik vissza a konstansra, ha egy régi fájlból hiányzik.
    """
    from qds.constants import T1_CALIBRATED_US, T2_CALIBRATED_US
    from qds.model import fit_t1, fit_t2

    if not runs:
        raise ValueError("nincs futás")
    t1_cal = runs[0].get("t1_calibrated_us") or T1_CALIBRATED_US
    t2_cal = runs[0].get("t2_calibrated_us") or T2_CALIBRATED_US
    taus = np.asarray(taus_us, dtype=float)

    echo_by_tau = series_table(runs, "echo", taus_us)
    ctrl_by_tau = series_table(runs, "ctrl", taus_us)

    per_run = []
    for run in runs:
        t2 = fit_t2(taus, p0_series(run, "echo", taus_us), t1_cal)
        t1 = fit_t1(taus, p0_series(run, "ctrl", taus_us))
        per_run.append({
            "run": run.get("run"),
            "job_id": run.get("job_id"),
            "t2_eff_us": t2["t2_us"],
            "t2_stderr_us": t2["stderr_us"],
            "t1_eff_us": t1["t1_us"],
            "t1_stderr_us": t1["stderr_us"],
            "t2_ratio": (t2["t2_us"] / t2_cal) if t2["t2_us"] else None,
            "t1_ratio": (t1["t1_us"] / t1_cal) if t1["t1_us"] else None,
        })

    t2s = np.asarray([r["t2_eff_us"] for r in per_run if r["t2_eff_us"]], dtype=float)
    t1s = np.asarray([r["t1_eff_us"] for r in per_run if r["t1_eff_us"]], dtype=float)

    def _stats(arr):
        if arr.size == 0:
            return None, None, None
        mean = float(np.mean(arr))
        sd = float(np.std(arr, ddof=1)) if arr.size > 1 else 0.0
        sem = sd / np.sqrt(arr.size) if arr.size > 1 else 0.0
        return mean, sd, sem

    t2_mean, t2_sd, t2_sem = _stats(t2s)
    t1_mean, t1_sd, _ = _stats(t1s)

    monotonia = {}
    for arm, table, increasing in (("echo", echo_by_tau, False),
                                   ("ctrl", ctrl_by_tau, True)):
        ok = 0
        for i in range(len(runs)):
            vals = [table[tau][i] for tau in taus_us]
            if increasing:
                ok += all(vals[j] < vals[j + 1] for j in range(len(vals) - 1))
            else:
                ok += all(vals[j] > vals[j + 1] for j in range(len(vals) - 1))
        monotonia[arm] = ok

    return {
        "n_runs": len(runs),
        "t1_calibrated_us": t1_cal,
        "t2_calibrated_us": t2_cal,
        "job_ids": [r.get("job_id") for r in runs],
        "taus_us": list(taus_us),
        "echo_p0_per_run": {str(t): echo_by_tau[t] for t in taus_us},
        "ctrl_p0_per_run": {str(t): ctrl_by_tau[t] for t in taus_us},
        "echo_mean_pct": [float(np.nanmean(echo_by_tau[t])) for t in taus_us],
        "echo_std_pct": [float(np.nanstd(echo_by_tau[t], ddof=1))
                         if len(runs) > 1 else 0.0 for t in taus_us],
        "ctrl_mean_pct": [float(np.nanmean(ctrl_by_tau[t])) for t in taus_us],
        "ctrl_std_pct": [float(np.nanstd(ctrl_by_tau[t], ddof=1))
                         if len(runs) > 1 else 0.0 for t in taus_us],
        "per_run": per_run,
        "t2_eff_per_run_us": [r["t2_eff_us"] for r in per_run],
        "t2_eff_mean_us": t2_mean,
        "t2_eff_std_us": t2_sd,
        "t2_eff_sem_us": t2_sem,
        "t1_eff_per_run_us": [r["t1_eff_us"] for r in per_run],
        "t1_eff_mean_us": t1_mean,
        "t1_eff_std_us": t1_sd,
        "monotonia_runs_ok": monotonia,
    }


def heterogeneity_chi2(values, errors, null_mean=None):
    """Futások közötti ingadozás chi²-tesztje (``qds_detectability.py`` alapja).

    Args:
        values: futásonkénti értékek (pl. T2_eff µs-ban).
        errors: futásonkénti standard hibák (a futás illesztési hibája).
        null_mean: a várt középérték; ha ``None``, a minta átlaga.

    Returns:
        dict: ``chi2``, ``dof``, ``p_value``, ``mean``, ``sd``, ``sem``,
        ``avg_stderr``, ``verdict`` (szöveges, a p<0,01 küszöbbel).
    """
    from scipy import stats

    x = np.asarray(values, dtype=float)
    se = np.asarray(errors, dtype=float)
    if x.size != se.size:
        raise ValueError("a values és az errors hossza különbözik")
    if x.size < 2:
        raise ValueError("legalább 2 futás kell a chi²-teszthez")
    mean = float(np.mean(x)) if null_mean is None else float(null_mean)
    chi2 = float(np.sum((x - mean) ** 2 / se ** 2))
    dof = x.size - 1
    p = float(1 - stats.chi2.cdf(chi2, dof))
    return {
        "chi2": chi2,
        "dof": dof,
        "p_value": p,
        "mean": float(np.mean(x)),
        "sd": float(np.std(x, ddof=1)),
        "sem": float(np.std(x, ddof=1)) / np.sqrt(x.size),
        "avg_stderr": float(np.mean(se)),
        "verdict": ("NEM fér bele a számított zajba" if p < 0.01
                    else "nem döntő (belefér a zajba)"),
    }
