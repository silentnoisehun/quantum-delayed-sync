# -*- coding: utf-8 -*-
"""
QDS — hardveres Hahn-echo eredmeny KIERTEKELES (kvota nelkul)
============================================================
Bemenet: a befejezett job nyers eredmenye (results/qam_echo_<JOB>.json)
A sorrend a bekuldés sorrendje: tau0 echo, tau0 ctrl, tau10 echo, ...

A kulcs kerdes — a TAU-TENGELY JO-E?
  A platform dt=4 ns-t ir (250 MHz), ami egy 5 GHz-es qubiten fizikailag
  lehetetlen. Ha a QPU mas aranyban szamol, a meret egy 18x-vel elcsuszott
  tau-skalat adna. Ezt az ILLESZTETT T2-vel deritjuk ki: ha a meres a
  kalibralt T2=121.3 us-hoz illeszkedik, a tengely rendben volt.
"""
import json, os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
JOB_ID = 'dba0q2gc77vs738252kg'
TAUS_US = [0, 10, 25, 50, 100, 200, 400, 800]
T1 = 254.1627621299776e-6      # a 91. qubit KALIBRALT T1-je
T2_CAL = 121.25600306875533e-6  # a 91. qubit KALIBRALT T2-je


def analytic(tau_s, t1, t2, theta):
    c, s2 = np.cos(theta), np.sin(theta) ** 2
    e1 = np.exp(-tau_s / t1) if t1 else 1.0
    e2 = np.exp(-tau_s / t2)
    return (0.5 + 0.5 * (e2 * s2 + e1 * c * c + c * (1 - e1)),
            0.5 + 0.5 * (1 + (c - 1) * e1))


def main():
    path = os.path.join('results', f'qam_echo_{JOB_ID}.json')
    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    rows = data['rows']
    assert len(rows) == 2 * len(TAUS_US), 'sorszam-eltérés a beküldéshez'

    theta = 2.353304971691044
    echo = {TAUS_US[i]: rows[2 * i]['p0'] for i in range(len(TAUS_US))}
    ctrl = {TAUS_US[i]: rows[2 * i + 1]['p0'] for i in range(len(TAUS_US))}

    print(f'Job: {JOB_ID}   backend={data["backend"]}   qubit={data["qubit"]}')
    print('=' * 78)
    print(' tau(us) | echo MERT | echo MODELL | kulonb. | ctrl MERT | ctrl MODELL | kulonb.')
    print('-' * 78)
    exp_e, exp_c = {}, {}
    for t in TAUS_US:
        pe, pc = analytic(t * 1e-6, T1, T2_CAL, theta)
        pe, pc = pe * 100, pc * 100
        exp_e[t], exp_c[t] = pe, pc
        print(f' {t:>7} | {echo[t]:>10.2f} | {pe:>12.2f} | {echo[t]-pe:>+8.2f} | '
              f'{ctrl[t]:>9.2f} | {pc:>11.2f} | {ctrl[t]-pc:>+8.2f}')

    # --- ILLESZTETT T2 (a tau-tengely onvizsgalata) -------------------------
    from scipy.optimize import curve_fit
    c, s2 = np.cos(theta), np.sin(theta) ** 2
    ts = np.array([t * 1e-6 for t in TAUS_US])
    y = np.array([echo[t] for t in TAUS_US]) / 100.0

    def model(t, t2):
        e1 = np.exp(-t / T1)
        return 0.5 + 0.5 * (np.exp(-t / t2) * s2 + e1 * c * c + c * (1 - e1))

    mask = ts > 0
    popt, pcov = curve_fit(model, ts[mask], y[mask], p0=[150e-6],
                           bounds=([1e-8], [20e-3]))
    t2_eff = float(popt[0])
    perr = float(np.sqrt(pcov[0][0]))
    pred = model(ts[mask], t2_eff) * 100
    rms = float(np.sqrt(np.mean((y[mask] * 100 - pred) ** 2)))
    axis = t2_eff / T2_CAL

    print('=' * 78)
    print(f'Kalibralt T2 : {T2_CAL*1e6:.2f} us  (T1 = {T1*1e6:.2f} us)')
    print(f'Illesztett T2: {t2_eff*1e6:.2f} +/- {perr*1e6:.2f} us   (RMS {rms:.2f} %)')
    print(f'TAU-TENGELY : arany = {axis:.3f}')
    verdict = ('RENDBEN — a dt-felteves helyes volt'
               if 0.85 < axis < 1.18 else
               'ELTORES — a platform dt-je NEM a QPU valodi ideozitasa')
    print(f'             -> {verdict}')
    print('-' * 78)
    mono_e = all(echo[TAUS_US[i]] > echo[TAUS_US[i + 1]] for i in range(len(TAUS_US) - 1))
    mono_c = all(ctrl[TAUS_US[i]] < ctrl[TAUS_US[i + 1]] for i in range(len(TAUS_US) - 1))
    print(f'Ervenyes meresfeltetelek:')
    print(f'  1. Kontroll monoton no        : {"IGEN" if mono_c else "NEM"}')
    print(f'  2. Echo monoton csokken        : {"IGEN" if mono_e else "NEM"}')
    print(f'  3. tau=0 echo ~100%           : {"IGEN" if echo[0] > 98 else "NEM"} '
          f'({echo[0]:.2f}%)')
    print(f'  4. tau=0 ctrl ~14.75%         : '
          f'{"IGEN" if abs(ctrl[0]-14.75) < 1.5 else "NEM"} ({ctrl[0]:.2f}%)')

    # --- kvota ---------------------------------------------------------------
    try:
        from qiskit_ibm_runtime import QiskitRuntimeService
        tp = os.environ.get('IBM_TOKEN_PATH', os.path.join(HERE, 'ibm_token.json'))
        with open(tp, encoding='utf-8') as f:
            tok = json.load(f)['apikey']
        svc = QiskitRuntimeService(channel='ibm_quantum_platform', token=tok,
                                   instance='auto')
        u = svc.usage()
        print('-' * 78)
        print(f'KVOTA: felhasznalva {u["usage_consumed_seconds"]} s / '
              f'{u["usage_limit_seconds"]} s   (maradt {u["usage_remaining_seconds"]} s)')
    except Exception as e:  # noqa: BLE001
        print(f'kvota lekérdezés hiba: {e}')

    out = {
        'job_id': JOB_ID, 'backend': 'ibm_kingston', 'qubit': 91,
        'theta': theta, 'shots': 1024,
        't1_calibrated_us': T1 * 1e6, 't2_calibrated_us': T2_CAL * 1e6,
        't2_fitted_us': t2_eff * 1e6, 't2_fitted_stderr_us': perr * 1e6,
        'tau_axis_ratio': axis, 'fit_rms_pct': rms,
        'tau_us': TAUS_US,
        'echo_measured_pct': [echo[t] for t in TAUS_US],
        'echo_model_pct': [exp_e[t] for t in TAUS_US],
        'ctrl_measured_pct': [ctrl[t] for t in TAUS_US],
        'ctrl_model_pct': [exp_c[t] for t in TAUS_US],
        'raw_counts': [r['counts'] for r in rows],
    }
    path2 = os.path.join('results', 'qam_echo_t2_results.json')
    with open(path2, 'w', encoding='utf-8') as f:
        json.dump(out, f, indent=2)
    print(f'mentve: {path2}')


if __name__ == '__main__':
    main()