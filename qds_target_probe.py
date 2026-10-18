# -*- coding: utf-8 -*-
"""
QDS — hardver elővizsgálat 2. (KVÓTA NÉLKÜL)
============================================
Cél: a valódi dt / granularity, a cel-qubit (91) életképessége,
és ha az rossz, a legjobb T2-es qubit kiválasztása.

NEM indit QPU jobot -> nem fogyaszt kvotát.
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
TARGET_BACKEND = os.environ.get('QDS_BACKEND', 'ibm_kingston')
QUBIT = int(os.environ.get('QDS_QUBIT', '91'))


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
    tgt = backend.target
    print('=' * 70)
    print(f'Backend: {TARGET_BACKEND}   num_qubits={backend.num_qubits}')

    # --- idozitas ------------------------------------------------------------
    dt = getattr(backend, 'dt', None)
    tdt = getattr(tgt, 'dt', None)
    print(f'backend.dt      = {dt}')
    print(f'target.dt       = {tdt}')
    print(f'target.granularity = {getattr(tgt, "granularity", None)}')
    print(f'target.pulse_alignment = {getattr(tgt, "pulse_alignment", None)}')
    eff_dt = tdt or dt
    if eff_dt:
        print(f'  -> 1 dt = {eff_dt*1e9:.4f} ns;  '
              f'a 10 us varakozas = {10e-6/eff_dt:.1f} dt')
        print(f'  -> 800 us varakozas = {800e-6/eff_dt:.1f} dt  '
              f'(granulaciohoz igazitva: '
              f'{int(800e-6/eff_dt)//max(1,getattr(tgt,"granularity",1) or 1)}'
              f' x gran)')
    else:
        print('  -> dt ISMERETLEN: a tau->dt konverzio nem biztonsagos!')

    # --- qubit 91 ------------------------------------------------------------
    print('-' * 70)
    qprops = getattr(tgt, 'qubit_properties', None)
    print(f'qubit_properties lista hossza: {len(qprops) if qprops else 0}')
    p91 = qprops[QUBIT] if qprops and QUBIT < len(qprops) else None
    print(f'Qubit {QUBIT} target.qubit_properties: {p91}')
    p91b = None
    try:
        p91b = backend.qubit_properties(QUBIT)
    except Exception as e:  # noqa: BLE001
        print(f'backend.qubit_properties({QUBIT}) hiba: {e}')
    print(f'Qubit {QUBIT} backend.qubit_properties: {p91b}')

    # --- mukodo qubitek ------------------------------------------------------
    print('-' * 70)
    good = []
    if qprops:
        for i, p in enumerate(qprops):
            if p is None:
                continue
            t1 = getattr(p, 't1', None)
            t2 = getattr(p, 't2', None)
            if t1 and t2:
                good.append((i, t1, t2, getattr(p, 'frequency', None)))
    print(f'Valtas maghul korlatozott T1/T2-vel: {len(good)} / {len(qprops or [])}')
    if good:
        best = sorted(good, key=lambda x: -x[2])[:10]
        print('Legjobb 10 T2 szerint:')
        print('   qubit      T1(us)     T2(us)    freq(GHz)')
        for i, t1, t2, f in best:
            fs = f'{f/1e9:8.4f}' if f else '     n/a'
            mark = ' <== CEL' if i == QUBIT else ''
            print(f'   {i:>5}  {t1*1e6:8.1f}  {t2*1e6:9.1f}   {fs}{mark}')
        if not any(g[0] == QUBIT for g in good):
            print(f'\n>>> A {QUBIT}. QUBIT NEM szerepel a mukodo listaban!')
            print(f'>>> Legjobb alternatíva: qubit {best[0][0]} '
                  f'(T2={best[0][2]*1e6:.1f} us)')
        else:
            sel = next(g for g in good if g[0] == QUBIT)
            rank = sorted(good, key=lambda x: -x[2]).index(sel) + 1
            print(f'\n>>> A {QUBIT}. qubit mukodo, T2={sel[2]*1e6:.1f} us, '
                  f'rankia={rank}/{len(good)}')
    print('=' * 70)


if __name__ == '__main__':
    main()