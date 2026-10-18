# -*- coding: utf-8 -*-
"""
QDS — dt-igazolas a MAR MEGFIZETT jobokból (KVÓTA NÉLKÜL)
==========================================================
Kerdes: a platform dt=4 ns-ot ir. 4 ns = 250 MHz -> fizikailag
NEM LEHET egy 5 GHz-os qubit sampling rate-je. A valodi dt valoszinusuleg
~0.222 ns (Eagle r3). Ezt a mar befizetett jobok ISA-k-circuitjeinek
muvelet-idotartamaibol lehet eldonteni:

  ha az sx gate 40 dt es a valodi hossza 40 * 0.222 ns = 8.9 ns
  -> a QPU 0.222 ns/dt-vel szamol, a 4 ns csak egy nominalis default.

NEM indit uj jobot -> nem fogyaszt kvotat.
"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
TARGET_BACKEND = os.environ.get('QDS_BACKEND', 'ibm_kingston')


def svc_connect():
    from qiskit_ibm_runtime import QiskitRuntimeService
    path = os.environ.get('IBM_TOKEN_PATH', os.path.join(HERE, 'ibm_token.json'))
    with open(path, encoding='utf-8') as f:
        token = json.load(f)['apikey']
    return QiskitRuntimeService(channel='ibm_quantum_platform', token=token,
                                instance='auto')


def main():
    svc = svc_connect()
    backend = svc.backend(name=TARGET_BACKEND)
    rep_dt = backend.dt
    print(f'{TARGET_BACKEND}: backend.dt = {rep_dt} s ({rep_dt*1e9:.3f} ns)')
    print('=' * 72)

    # --- 1. probaljuk a pulse defaults-ot (ha elerheto) ----------------------
    try:
        d = backend.defaults()
        print(f'defaults.dt          = {d.dt}')
        print(f'defaults.granularity = {d.granularity}')
        print(f'defaults.instruction_durations szamalanak kulcsai: '
              f'{list(d.instruction_durations.keys())[:8]}')
        try:
            for k, v in d.instruction_durations.items():
                for q, dur in v.items():
                    print(f'   {k} q{q}: {dur} dt -> {dur*d.dt*1e9:.2f} ns')
                if k == 'sx':
                    break
        except Exception as e:  # noqa: BLE001
            print('  (duration-reszletek nem olvashatok:', e, ')')
    except Exception as e:  # noqa: BLE001
        print(f'defaults() nem erheto el ({type(e).__name__}: {e})')
    print('-' * 72)

    # --- 2. a mar befizetett jobok ISA circuitjei ----------------------------
    try:
        jobs = svc.jobs(limit=8)
    except Exception as e:  # noqa: BLE001
        print(f'jobs() nem elerheto: {e}')
        jobs = []
    print(f'Korábbi jobok: {len(jobs)}')
    proven = False
    for job in jobs:
        print(f'\n--- job {job.job_id()}  status={job.status()} '
              f'backend={job.backend().name}')
        if job.status() != 'DONE':
            continue
        try:
            res = job.result()
        except Exception as e:  # noqa: BLE001
            print(f'   result nem elerheto: {e}')
            continue
        prims = res[0] if isinstance(res, (list, tuple)) else res
        meta = getattr(prims, 'metadata', None)
        isa = (meta or {}).get('isa')
        if not isa:
            print('   nincs ISA metadata ebben a jobban')
            continue
        print(f'   target.dt az ISA-ban: {isa.get("dt")}  '
              f'granularity: {isa.get("granularity")}')
        for circ in isa.get('circuits', [])[:1]:
            ops = circ.get('operations', [])
            print(f'   {len(ops)} muvelet, keselyozok: '
                  f'{circ.get("name")}')
            seen = {}
            for op in ops:
                key = op.get('name')
                if key in ('barrier', 'measure', 'delay'):
                    continue
                seen.setdefault(key, op.get('duration'))
            for k, dur in seen.items():
                if dur:
                    for cand in (2.222e-10, 4e-09):
                        ns = dur * cand * 1e9
                        print(f'      {k:<8} {dur:>5} dt = {ns:8.2f} ns '
                              f'(ha dt={cand*1e9:.3f} ns)')
            if seen and not proven:
                proven = True
        # ugyanott a delay muvelet hossza a sajat fizikai tau-nk?
        for circ in isa.get('circuits', []):
            for op in circ.get('operations', []):
                if op.get('name') == 'delay' and op.get('duration'):
                    print(f'   DELAY {op["duration"]} dt; '
                          f'ha dt=0.222ns -> '
                          f'{op["duration"]*2.222e-10*1e6:.3f} us, '
                          f'ha dt=4ns -> {op["duration"]*4e-9*1e6:.3f} us')
                    break
            else:
                continue
            break

    print('=' * 72)
    print('Ha az sx kb. 8-9 ns-nak adodik dt=0.222 ns-sel, akkor a platform')
    print('4 ns-os dt-je NEM az igazi idozitas -> a tau-t MICROSECUND-BAN kell')
    print('megadni az aramkorben, es a transz[p]ilerrel kell dt-vale konvertalni.')


if __name__ == '__main__':
    main()