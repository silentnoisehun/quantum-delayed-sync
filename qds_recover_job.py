# -*- coding: utf-8 -*-
"""
QDS — befejezett job eredmenyeinek VISSZAKERESE (KVÓTA NÉLKÜL)
============================================================
A hahn_echo_t2_qam.py a job lefutasa UTAN hibadt el az eredmények
olvasasakor (`pub.data[0]` -> KeyError). A QPU-n a merés NEM futott
fel: a job kesz, az adatok a job ID-bel ujrak erhetoek, ezért NEM
kell (nem szabad) uj jobot kuldeni.

Hasznalat:
  .venv-qds\\Scripts\\python.exe qds_recover_job.py [JOB_ID]
"""
import json, os, sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
JOB_ID = (sys.argv[1] if len(sys.argv) > 1
          else 'dba0q2gc77vs738252kg').strip()
QUBIT = 91
SHOTS = 1024


def svc_connect():
    from qiskit_ibm_runtime import QiskitRuntimeService
    path = os.environ.get('IBM_TOKEN_PATH', os.path.join(HERE, 'ibm_token.json'))
    with open(path, encoding='utf-8') as f:
        token = json.load(f)['apikey']
    return QiskitRuntimeService(channel='ibm_quantum_platform', token=token,
                                instance='auto')


def first_counts(pub):
    """Qiskit 2.x: a data bin KULCS a regiszternev ('meas'), nem az index.
    A 0.6-os gyakorlat `pub.data[0]` KeyError-t dob -> itt robustan
    keressuk az egyetlen (vagy az utolso nemures) bin-t."""
    data = pub.data
    for name in data.keys():
        try:
            c = data[name].get_counts()
        except Exception:  # noqa: BLE001
            continue
        if c:
            return name, c
    raise RuntimeError(f'ures data bin a jobban: {list(data.keys())}')


def main():
    svc = svc_connect()
    job = svc.job(JOB_ID)
    print(f'Job {JOB_ID}: status={job.status()}  backend={job.backend().name}')
    if job.status() != 'DONE':
        print('A job még nem kesz.')
        return
    res = job.result()
    print(f'{len(res)} publikacio')

    rows, isa_meta = [], None
    for i, pub in enumerate(res):
        bin_name, counts = first_counts(pub)
        total = sum(counts.values())
        p0 = counts.get('0', 0) / total * 100
        name = getattr(getattr(pub, 'metadata', {}), 'get', lambda k: None)('circuit_metadata') or {}
        cm = (name or {}).get('qds', {})
        rows.append({'pub': i, 'bin': bin_name, 'total': total,
                     'p0': p0, 'counts': dict(counts),
                     'tau_us': cm.get('tau_us'), 'arm': cm.get('arm')})
        if isa_meta is None and pub.metadata:
            isa_meta = pub.metadata.get('isa')

    print('=' * 74)
    print(f'sor | reg | tau(us) | kar     | P(0)%  | 0-egysegek / total')
    for r in rows:
        print(f'{r["pub"]:>3} | {r["bin"]:<4} | '
              f'{str(r["tau_us"]):>7} | {str(r["arm"]):<6} | '
              f'{r["p0"]:>6.2f} | {r["counts"].get("0",0):>5} / {r["total"]}')

    os.makedirs('results', exist_ok=True)
    with open(os.path.join('results', f'qam_echo_{JOB_ID}.json'), 'w',
              encoding='utf-8') as f:
        json.dump({'job_id': JOB_ID, 'backend': 'ibm_kingston',
                   'qubit': QUBIT, 'rows': rows,
                   'isa': {'dt': (isa_meta or {}).get('dt'),
                           'granularity': (isa_meta or {}).get('granularity')}},
                  f, indent=2)
    print(f'\nmentve: results/qam_echo_{JOB_ID}.json')
    print(f'ISA dt = {(isa_meta or {}).get("dt")} s, '
          f'granularity = {(isa_meta or {}).get("granularity")}')


if __name__ == '__main__':
    main()