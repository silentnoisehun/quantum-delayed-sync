# -*- coding: utf-8 -*-
"""
CROSS-REPO TESZT — a QDS drift-találata bejáratja a wave-quantum ⟨ZZ⟩ csatornát
=================================================================================
Kérdés: a QDS 5 futása kimutatta, hogy a 91-es qubit FÁZIS-KOHERENCIÁJA
(T2_eff) 43–141 us között ingadozik percenként — 3,62x a mérési zajon túl.
Ha ez a drift uralja a programot, akkor a wave-quantum ⟨ZZ⟩ csatornájának
Pearson-rje is erősen ingadozik futásról futásra.

Ha viszont az r STABIL, akkor a hipotézis HAMIS: a drift a 91-es qubit
specifikus problémája, nem a program általános korlátja.

Áramkör: a wave_quantum_v3.py `build_v3` / `run_theorem_sweep` szerint
(13 partner qubit, readout=0, partner=1, 13 sáv, X-bázisú kiolvasás),
a run7 rögzített fizikai layoutjával.

Nem használunk tokent a fájlból közvetlenül a repónak; a token a helyi
ibm_token.json-ból jön (nem kerül a repóba).

Használat:
  .venv-qds\\Scripts\\python.exe qds_wavezz_repeat.py --runs 5 --delay 75
"""
import argparse, json, math, os, time

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, 'results')
BACKEND = 'ibm_kingston'
N_BANDS = 13
N_QUBITS = 14
# a wave-quantum run7 rögzített layoutja (a repo wave_quantum_v3.py-jából)
WAVE_PHYS = [107, 106, 105, 108, 109, 110, 111, 98, 91, 92, 93, 94, 95, 99]
A_AMP = 0.5


def svc_connect():
    from qiskit_ibm_runtime import QiskitRuntimeService
    path = os.environ.get('IBM_TOKEN_PATH', os.path.join(HERE, 'ibm_token.json'))
    with open(path, encoding='utf-8') as f:
        tok = json.load(f)['apikey']
    return QiskitRuntimeService(channel='ibm_quantum_platform', token=tok,
                                instance='auto')


def pick_layout(backend):
    """A wave-quantum layoutját ellenőrizzük a backenden; a 0 és 1
    (readout, partner) a lényeges — ha azok nem élnek, közeli jó párt keresünk."""
    props = getattr(backend.target, 'qubit_properties', None)
    alive = []
    if props:
        alive = [i for i, p in enumerate(props) if p is not None and p.t1 and p.t2]
    dead = [q for q in WAVE_PHYS if q not in alive]
    if not dead:
        print(f'layout: a wave-quantum fizikai layoutja ({WAVE_PHYS}) elerheto, '
              f'hasznajuk.')
        return list(WAVE_PHYS)
    print(f'layout: {len(dead)} qubit a wave-layoutbol nem mukodik itt: {dead}')
    # readout/partner parancs: ket egymas melletti, jo T2-vel rendelkezo qubit
    cand = [i for i in alive if (i + 1) in alive]
    cand.sort(key=lambda i: -(props[i].t2 + props[i + 1].t2))
    pair = cand[0] if cand else alive[:2]
    rest = [q for q in alive if q not in pair][:N_QUBITS - 2]
    layout = [pair[0], pair[1]] + rest
    print(f'layout: helyettesito parancs: readout={pair[0]} partner={pair[1]}, '
          f'T2={props[pair[0]].t2*1e6:.0f}/{props[pair[1]].t2*1e6:.0f} us')
    return layout


def build_param_circuit():
    from qiskit import QuantumCircuit
    from qiskit.circuit import Parameter
    bands = [Parameter(f'b_{i}') for i in range(N_BANDS)]
    th_a, th_phi = Parameter('A_t'), Parameter('phi_t')
    qc = QuantumCircuit(N_QUBITS, 2)
    qc.ry(th_a, 0)
    for i, q in enumerate(range(1, N_QUBITS)):
        qc.rx(bands[i], q)
    qc.rz(th_phi, 0)
    for q in range(1, N_QUBITS):
        qc.h(q)
        qc.cx(q, 0)
    qc.h(0)
    qc.h(1)
    qc.measure(0, 0)
    qc.measure(1, 1)
    return qc, bands, th_a, th_phi


def zz_of(counts, shots):
    p = {k: counts.get(k, 0) / shots for k in ('00', '01', '10', '11')}
    return (p['00'] + p['11']) - (p['01'] + p['10']), p


def pearson(x, y):
    n = len(x)
    mx, my = sum(x) / n, sum(y) / n
    sxy = sum((a - mx) * (b - my) for a, b in zip(x, y))
    sxx = sum((a - mx) ** 2 for a in x)
    syy = sum((b - my) ** 2 for b in y)
    return sxy / math.sqrt(sxx * syy)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--runs', type=int, default=5)
    ap.add_argument('--delay', type=int, default=75)
    ap.add_argument('--shots', type=int, default=2048)
    args = ap.parse_args()
    os.makedirs(RESULTS, exist_ok=True)

    from qiskit import transpile
    from qiskit_ibm_runtime import SamplerV2

    svc = svc_connect()
    backend = svc.backend(name=BACKEND)
    layout = pick_layout(backend)
    qc, bands, th_a, th_phi = build_param_circuit()
    tqc = transpile(qc, backend=backend, initial_layout=layout,
                    optimization_level=3, seed_transpiler=42)
    print(f'transzpiler: {tqc.depth() } depth, layout={layout[:3]}...')

    theory = [math.cos(2.0 * math.pi * k / N_BANDS) for k in range(N_BANDS)]
    results = []
    for run in range(1, args.runs + 1):
        if run > 1:
            print(f'... {args.delay} s varakozas (az idobeli drift a cel)')
            time.sleep(args.delay)
        circuits = []
        for k in range(N_BANDS):
            ang = 2.0 * math.pi * k / N_BANDS
            binds = {th_a: 2.0 * math.asin(math.sqrt(A_AMP)), th_phi: 0.0}
            for p in bands:
                binds[p] = ang
            c = tqc.assign_parameters(binds)
            c.metadata = {'band': k}
            circuits.append(c)
        t0 = time.time()
        job = SamplerV2(mode=backend).run(circuits, shots=args.shots)
        print(f'run{run}: bekuldve {job.job_id()} ...')
        res = job.result()
        rows, meas, wcs = [], [], []
        for k, c in enumerate(circuits):
            counts = {}
            for nm in res[k].data.keys():
                cc = res[k].data[nm].get_counts()
                if cc:
                    counts = cc
                    break
            zz, probs = zz_of(counts, args.shots)
            meas.append(zz)
            rows.append({'band': k, 'measured_zz': zz,
                         'theory_zz': theory[k], 'counts': dict(counts)})
        r = pearson(theory, meas)
        results.append({'run': run, 'job_id': job.job_id(),
                        'submitted_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ',
                                                       time.gmtime(t0)),
                        'pearson_r': r, 'rows': rows})
        fn = os.path.join(RESULTS, f'wave_zz_repeat_run{run}.json')
        with open(fn, 'w', encoding='utf-8') as f:
            json.dump({'backend': BACKEND, 'shots': args.shots,
                       'layout': layout, 'source': 'wave_quantum_v3.py build_v3',
                       'pearson_r': r, 'job_id': job.job_id(),
                       'run': run, 'rows': rows}, f, indent=2)
        print(f'run{run}: r = {r:.4f}   zorat: ' +
              ' '.join(f'{m:+.3f}' for m in meas))
        try:
            u = svc.usage()
            print(f'   kvota: {u["usage_consumed_seconds"]}/{u["usage_limit_seconds"]} s '
                  f'(maradt {u["usage_remaining_seconds"]})')
        except Exception:  # noqa: BLE001
            pass

    rs = [x['pearson_r'] for x in results]
    mean, sd = sum(rs) / len(rs), (sum((v - mean) ** 2 for v in rs) /
                                    (len(rs) - 1)) ** 0.5
    print('=' * 72)
    print('PEARSON r futasonkent: ' + '  '.join(f'{v:.4f}' for v in rs))
    print(f'atlag {mean:.4f}  szoras {sd:.4f}  (relativ szoras {sd/mean*100:.1f}%)')
    print()
    print('OSSZEHASONLITAS a QDS T2_eff szorasaval:')
    print('  QDS T2_eff  : atlag 89.6 us, szoras 39.2 us -> 43.7% relativ')
    print(f'  wave ZZ r   : atlag {mean:.4f}, szoras {sd:.4f} -> {sd/mean*100:.1f}% relativ')
    verdict = ('AZ INGADOZAS AZONOS NAGYSAGRENDU — a drift a <ZZ> csatornat is '
               'uralja (a hipotezis TAMASZTOTT)'
               if (sd / mean) > 0.2 else
               'AZ r STABIL — a drift NEM hat a <ZZ> csatornara; a hipotezis '
               'HAMIS (a drift a 91-es qubit specifikus)')
    print(f'  -> {verdict}')
    with open(os.path.join(RESULTS, 'wave_zz_repeat_summary.json'), 'w',
              encoding='utf-8') as f:
        json.dump({'backend': BACKEND, 'shots': args.shots, 'layout': layout,
                   'pearson_r_per_run': rs, 'r_mean': mean, 'r_std': sd,
                   'r_relative_std_pct': sd / mean * 100,
                   'qds_t2eff_relative_std_pct': 43.7,
                   'verdict': verdict, 'runs': results}, f, indent=2)
    print('mentve: results/wave_zz_repeat_summary.json')


if __name__ == '__main__':
    main()