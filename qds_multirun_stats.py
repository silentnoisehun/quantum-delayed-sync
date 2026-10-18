# -*- coding: utf-8 -*-
"""
QDS — tobb futas statisztikaja (biraloi szintu)
===============================================
Egy futasbol nincs T2 hibasav: egyetlen pont 1024 shotbol ~1%.
Az N futas atlaganak szoraja VISZONT a tenyleges idobeli ingadozast
megyi — es ez a drift-magyanaz a lep, amit az echo kar integral.

Kimenet:
  results/multirun_stats.json
  + szoveges osszegzes a stdout-on

A kiirheto kovetkeztetesek hatarai a docs/QDS_REFEREE_STATS.md-ban vannak.
"""
import glob, json, os, re

import numpy as np
from scipy.optimize import curve_fit

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, 'results')
TAUS = [0, 10, 25, 50, 100, 200, 400, 800]
THETA = 2.353304971691044


def load_runs():
    runs = []
    path = os.path.join(RESULTS, 'raw_counts_all_runs.json')
    if not os.path.exists(path):
        for fn in sorted(glob.glob(os.path.join(RESULTS, 'result_run*.json'))):
            with open(fn, encoding='utf-8') as f:
                runs.append(json.load(f))
        return runs
    with open(path, encoding='utf-8') as f:
        merged = json.load(f)
    for fn in sorted(merged.keys(), key=lambda s: int(re.search(r'run(\d+)', s).group(1))):
        runs.append(merged[fn])
    return runs


def fit_t2(t, y, t1):
    c, s2 = np.cos(THETA), np.sin(THETA) ** 2

    def model(tt, t2):
        e1 = np.exp(-tt / t1)
        return 0.5 + 0.5 * (np.exp(-tt / t2) * s2 + e1 * c * c + c * (1 - e1))
    m = t > 0
    try:
        p, cov = curve_fit(model, t[m], y[m], p0=[150e-6], bounds=([1e-8], [20e-3]))
        return float(p[0]), float(np.sqrt(cov[0][0]))
    except Exception:  # noqa: BLE001
        return None, None


def fit_t1(t, y):
    c = np.cos(THETA)

    def model(tt, t1, off=0.0):
        return 0.5 + 0.5 * (1 + (c - 1) * np.exp(-tt / t1)) + off
    m = t > 0
    try:
        p, cov = curve_fit(model, t[m], y[m], p0=[250e-6, 0.0],
                           bounds=([50e-6, -0.02], [1e-3, 0.02]))
        return float(p[0]), float(np.sqrt(cov[0][0]))
    except Exception:  # noqa: BLE001
        return None, None


def main():
    runs = load_runs()
    print(f'{len(runs)} futas talalhato')
    if not runs:
        return
    t1_cal = runs[0].get('t1_calibrated_us') or 254.1627621299776
    t2_cal = runs[0].get('t2_calibrated_us') or 121.25600306875533
    print(f'kalibralt: T1={t1_cal:.1f} us  T2={t2_cal:.1f} us')
    print('=' * 92)

    print('ECHO kar — P(0)% futasonkent, atlag +- szoras')
    hdr = ' tau(us) | ' + ' | '.join(f'run{r.get("run","?")}' for r in runs) + ' |   atlag +- szor'
    print(hdr)
    print('-' * 92)
    echo_by_tau, ctrl_by_tau = {}, {}
    for ti, tau in enumerate(TAUS):
        vals = []
        for r in runs:
            e = [p['p0_pct'] for p in r['points']
                 if p['arm'] == 'echo' and p['tau_us'] == tau]
            vals.append(e[0] if e else np.nan)
        echo_by_tau[tau] = vals
        m, s = np.nanmean(vals), np.nanstd(vals, ddof=1) if len(vals) > 1 else 0.0
        cells = ' | '.join(f'{v:6.2f}' for v in vals)
        print(f' {tau:>7} | {cells} | {m:8.2f} +- {s:4.2f}')
    print('-' * 92)
    print('KONTROLL kar — P(0)% futasonkent, atlag +- szoras')
    for tau in TAUS:
        vals = []
        for r in runs:
            e = [p['p0_pct'] for p in r['points']
                 if p['arm'] == 'ctrl' and p['tau_us'] == tau]
            vals.append(e[0] if e else np.nan)
        ctrl_by_tau[tau] = vals
        m, s = np.nanmean(vals), np.nanstd(vals, ddof=1) if len(vals) > 1 else 0.0
        cells = ' | '.join(f'{v:6.2f}' for v in vals)
        print(f' {tau:>7} | {cells} | {m:8.2f} +- {s:4.2f}')

    # --- per-run fit --------------------------------------------------------
    print('=' * 92)
    print('FUTASONKENTI ILLESZTETT IDOALLANDO')
    print(' run | job_id                 | T2_eff(us)   | T1_eff(us)   | T2/T2kal | T1/T1kal')
    print('-' * 92)
    t2s, t1s = [], []
    for r in runs:
        ts = np.array(TAUS, dtype=float) * 1e-6
        e = np.array([echo_by_tau[t][runs.index(r)] for t in TAUS], dtype=float) / 100
        c = np.array([ctrl_by_tau[t][runs.index(r)] for t in TAUS], dtype=float) / 100
        t2e, t2err = fit_t2(ts, e, t1_cal * 1e-6)
        t1e, t1err = fit_t1(ts, c)
        if t2e:
            t2s.append(t2e)
        if t1e:
            t1s.append(t1e)
        jid = r.get('job_id', '?')
        r2 = (t2e * 1e6 / t2_cal) if t2e else float('nan')
        r1 = (t1e * 1e6 / t1_cal) if t1e else float('nan')
        v2 = t2e * 1e6 if t2e else float('nan')
        v1 = t1e * 1e6 if t1e else float('nan')
        e2 = t2err * 1e6 if t2err else float('nan')
        e1 = t1err * 1e6 if t1err else float('nan')
        print(f' {r.get("run","?"):>3} | {jid:<22} | {v2:7.1f} +-{e2:4.1f} | '
              f'{v1:7.1f} +-{e1:4.1f} | {r2:8.3f} | {r1:8.3f}')

    if len(t2s) > 1:
        m2, s2_ = float(np.mean(t2s)), float(np.std(t2s, ddof=1))
        sem = s2_ / np.sqrt(len(t2s))
        print('-' * 92)
        print(f'T2_eff  atlag = {m2*1e6:.1f} +- {s2_*1e6:.1f} us (szoras, N={len(t2s)}), '
              f'felepo = +- {sem*1e6:.1f} us')
        print(f'         kalibralt T2 = {t2_cal:.1f} us -> arany = {m2*1e6/t2_cal:.3f} '
              f'+- {sem*1e6/t2_cal:.3f}')
        print(f'         a HIBAJAVITOTT atlag is a kalibraltonal KISEBB: '
              f'{(m2*1e6/t2_cal):.2f}x')
    if len(t1s) > 1:
        m1, s1_ = float(np.mean(t1s)), float(np.std(t1s, ddof=1))
        print(f'T1_eff  atlag = {m1*1e6:.1f} +- {s1_*1e6:.1f} us (N={len(t1s)}), '
              f'arany = {m1*1e6/t1_cal:.3f}')

    print('=' * 92)
    print('MONOTONIA — minden futasban ellenorzve')
    for label, series in (('echo', echo_by_tau), ('kontroll', ctrl_by_tau)):
        ok = 0
        for i in range(len(runs)):
            vals = [series[t][i] for t in TAUS]
            if label == 'echo':
                ok += all(vals[j] > vals[j + 1] for j in range(len(vals) - 1))
            else:
                ok += all(vals[j] < vals[j + 1] for j in range(len(vals) - 1))
        print(f'  {label:<9}: {ok}/{len(runs)} futas monoton')

    out = {
        'n_runs': len(runs),
        't1_calibrated_us': t1_cal, 't2_calibrated_us': t2_cal,
        'job_ids': [r.get('job_id') for r in runs],
        'taus_us': TAUS,
        'echo_p0_per_run': echo_by_tau,
        'ctrl_p0_per_run': ctrl_by_tau,
        'echo_mean_pct': [float(np.nanmean(echo_by_tau[t])) for t in TAUS],
        'echo_std_pct': [float(np.nanstd(echo_by_tau[t], ddof=1))
                         if len(runs) > 1 else 0.0 for t in TAUS],
        'ctrl_mean_pct': [float(np.nanmean(ctrl_by_tau[t])) for t in TAUS],
        'ctrl_std_pct': [float(np.nanstd(ctrl_by_tau[t], ddof=1))
                         if len(runs) > 1 else 0.0 for t in TAUS],
        't2_eff_per_run_us': [x * 1e6 for x in t2s],
        't2_eff_mean_us': float(np.mean(t2s)) * 1e6 if t2s else None,
        't2_eff_std_us': float(np.std(t2s, ddof=1)) * 1e6 if len(t2s) > 1 else None,
        't2_eff_sem_us': (float(np.std(t2s, ddof=1)) / np.sqrt(len(t2s))) * 1e6
        if len(t2s) > 1 else None,
    }
    with open(os.path.join(RESULTS, 'multirun_stats.json'), 'w',
              encoding='utf-8') as f:
        json.dump(out, f, indent=2)
    print('mentve: results/multirun_stats.json')


if __name__ == '__main__':
    main()