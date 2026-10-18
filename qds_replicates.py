# -*- coding: utf-8 -*-
"""
QDS — ISMETELT hardveres meresek (a wave-quantum runN konvencioja szerint)
==========================================================================
Miért: EGY futasbol nem lehet T2 hibasavot adni (sorosan egyetlen pont
pontontossaga 1024 shotbol ~1%). A "hetszer megmérni ugyanazt" gyakorlat
(wave-quantum: 7 futas) adja a hibasavot, ES kiderul, hogy a
frekvencia-drift idobeli stabil-e -> ez maga a QDS kerdes.

Minden futas EGY SEPARAT IBM JOB, igy valodi idokulonbsag van koztuk:
az idosbeli elcsuszakorlat is lathato.

Kiirasa a repoban:
  results/result_runN_kingston_1024.json    egy futas nyers adatai
  results/raw_counts_all_runs.json         osszes futas egy fajlban
  results/circuit_hashes.json              a sablon hash + mimesi megjegyzés

Hasznalat:
  .venv-qds\\Scripts\\python.exe qds_replicates.py --runs 4 --delay 75
"""
import argparse, hashlib, json, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
# a sablon IMPORTALASA garantalja, hogy minden futas UGyanazt az aramkort
# epiti (theta/phi/lam a seed=42-bol jon, es a tau-racs is fix)
from hahn_echo_t2_qam import build_circuits, theta, phi, lam, SHOTS, QUBIT

BACKEND = 'ibm_kingston'
TAUS = [0, 10, 25, 50, 100, 200, 400, 800]
RESULTS = os.path.join(HERE, 'results')

# A run1 mar futott (job dba0q2gc77vs738252kg) -> innen folytatjuk
RUN1_JOB = 'dba0q2gc77vs738252kg'


def svc_connect():
    from qiskit_ibm_runtime import QiskitRuntimeService
    path = os.environ.get('IBM_TOKEN_PATH', os.path.join(HERE, 'ibm_token.json'))
    with open(path, encoding='utf-8') as f:
        token = json.load(f)['apikey']
    return QiskitRuntimeService(channel='ibm_quantum_platform', token=token,
                                instance='auto')


def circuit_hash(circuits):
    """A sablon KANONIKUS utasitassorozatanak hash-e.

    A SamplerV2 a bekuldott ISA-aramkoroket NEM teszi lekerdezhetoeve
    (ezt a wave-quantum circuit_hashes.json-je is megjegyzi), ezert a
    hash a SABLONBOL keszul, nem a job visszaadott aramkorabol. Ez
    bizonyitja, hogy minden futas azonos fizikai lancat epitett."""
    parts = []
    for tau, dur, qc_e, qc_c in circuits:
        for arm, qc in (('echo', qc_e), ('ctrl', qc_c)):
            ops = [(i.operation.name, str(i.qubits), str(i.operation.params))
                   for i in qc.data]
            parts.append(f'{tau}|{arm}|' + ';'.join(
                f'{n},{q},{p}' for n, q, p in ops))
    return hashlib.sha256('\n'.join(parts).encode('utf-8')).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--runs', type=int, default=4, help='további futások száma')
    ap.add_argument('--delay', type=int, default=75,
                    help='másodperc két futás között (időbeli drift kimutatására)')
    ap.add_argument('--start', type=int, default=2, help='első futás sorszáma')
    args = ap.parse_args()

    os.makedirs(RESULTS, exist_ok=True)
    from qiskit import transpile
    from qiskit_ibm_runtime import SamplerV2

    svc = svc_connect()
    backend = svc.backend(name=BACKEND)
    t1 = t2 = None
    try:
        p = backend.qubit_properties(QUBIT)
        t1, t2 = p.t1, p.t2
    except Exception as e:  # noqa: BLE001
        print(f'kalibracio nem elerheto: {e}')

    circuits = build_circuits(dt=None, unit='us')
    chash = circuit_hash(circuits)
    print(f'guben sajonoshash: {chash[:16]}...  (theta={theta:.6f})')

    made = []
    for k in range(args.start, args.start + args.runs):
        if k > args.start:
            print(f'... {args.delay} s varakozas a drift kimutatásara')
            time.sleep(args.delay)
        pubs = []
        for tau, dur, qc_e, qc_c in circuits:
            for arm, qc in (('echo', qc_e), ('ctrl', qc_c)):
                tqc = transpile(qc, backend, optimization_level=0,
                                seed_transpiler=42, initial_layout=[QUBIT])
                tqc.metadata = {'qds': {'tau_us': tau, 'arm': arm,
                                        'delay_us': dur}}
                pubs.append(tqc)
        t_submit = time.time()
        sampler = SamplerV2(mode=backend)
        job = sampler.run([(qc,) for qc in pubs], shots=SHOTS)
        jid = job.job_id()
        print(f'run{k}: bekuldve {jid}, varakozas a QPU-ra...')
        res = job.result()
        elapsed = time.time() - t_submit

        points = []
        for i, qc in enumerate(pubs):
            pub = res[i]
            counts = {}
            for name in pub.data.keys():
                c = pub.data[name].get_counts()
                if c:
                    counts = c
                    break
            md = (qc.metadata or {}).get('qds', {})
            points.append({'tau_us': md.get('tau_us'), 'arm': md.get('arm'),
                           'counts': counts,
                           'p0_pct': counts.get('0', 0) / sum(counts.values()) * 100})
        rec = {'run': k, 'job_id': jid, 'backend': BACKEND, 'qubit': QUBIT,
               'shots': SHOTS, 'theta': theta, 'phi': phi, 'lam': lam,
               'submitted_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ',
                                              time.gmtime(t_submit)),
               'wall_seconds': round(elapsed, 1),
               't1_calibrated_us': t1 * 1e6 if t1 else None,
               't2_calibrated_us': t2 * 1e6 if t2 else None,
               'circuit_template_sha256': chash, 'points': points}
        fn = os.path.join(RESULTS, f'result_run{k}_kingston_{SHOTS}.json')
        with open(fn, 'w', encoding='utf-8') as f:
            json.dump(rec, f, indent=2)
        e = {p['tau_us']: p['p0_pct'] for p in points if p['arm'] == 'echo'}
        print(f'run{k}: {jid} kesz ({elapsed:.0f} s varakozas) -> {os.path.basename(fn)}')
        print('   echo: ' + ' '.join(f'{t}us={e[t]:.1f}%' for t in TAUS))
        made.append(k)

        try:
            u = svc.usage()
            print(f'   kvota: {u["usage_consumed_seconds"]}/'
                  f'{u["usage_limit_seconds"]} s '
                  f'(maradt {u["usage_remaining_seconds"]} s)')
        except Exception:  # noqa: BLE001
            pass

    print('=' * 70)
    print(f'kesz: run{made}')

    # --- run1 beemelése + osszesites ---------------------------------------
    merged = {}
    if os.path.exists(os.path.join(RESULTS, 'qam_echo_dba0q2gc77vs738252kg.json')):
        with open(os.path.join(RESULTS, 'qam_echo_dba0q2gc77vs738252kg.json'),
                  encoding='utf-8') as f:
            r1 = json.load(f)
        pts = [{'tau_us': TAUS[i], 'arm': a, 'counts': r1['rows'][2 * i + j]['counts'],
                'p0_pct': r1['rows'][2 * i + j]['p0']}
               for i in range(len(TAUS)) for j, a in ((0, 'echo'), (1, 'ctrl'))]
        merged['result_run1_kingston_1024.json'] = {
            'run': 1, 'job_id': RUN1_JOB, 'backend': BACKEND, 'qubit': QUBIT,
            'shots': SHOTS, 'theta': theta,
            'note': 'az elso futas; a bekuldes utan a parser elbukott, '
                    'az adatok job ID-ből kerültek vissza (nem futott ujra)',
            'points': pts}
    for fn in sorted(os.listdir(RESULTS)):
        if fn.startswith('result_run') and fn != 'result_run1_kingston_1024.json':
            with open(os.path.join(RESULTS, fn), encoding='utf-8') as f:
                merged[fn] = json.load(f)
    with open(os.path.join(RESULTS, 'raw_counts_all_runs.json'), 'w',
              encoding='utf-8') as f:
        json.dump(merged, f, indent=2)
    print(f'raw_counts_all_runs.json: {len(merged)} futas -> '
          f'{sorted(merged.keys())}')

    with open(os.path.join(RESULTS, 'circuit_hashes.json'), 'w',
              encoding='utf-8') as f:
        json.dump({
            'note': 'A hash a SABLON kanonikus utasitassorozatabol keszult, '
                    'nem a job visszaadott ISA-aramkorabol: a SamplerV2 a '
                    'bekuldott ISA-aramkoroket nem teszi lekerdezhetoeve. '
                    'Azonos hash = azonos fizikai lanc minden futasban.',
            'template_sha256': chash,
            'theta': theta, 'phi': phi, 'lam': lam,
            'shots': SHOTS, 'qubit': QUBIT, 'backend': BACKEND,
            'taus_us': TAUS,
            'delay_unit': 'us (a transzpiler konvertalja dt-re)',
        }, f, indent=2)
    print('circuit_hashes.json kiirva')


if __name__ == '__main__':
    main()