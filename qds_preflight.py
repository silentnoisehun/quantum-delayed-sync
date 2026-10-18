# -*- coding: utf-8 -*-
"""
QDS — hardver elővizsgálat (KVÓTA NÉLKÜL)
========================================
Ez a script NEM futtat QPU jobot: nem fogyaszt IBM kvótát.
Csak a backend-lista, a qubit-adatok és a kvóta megállapítása történik.

Használat:  .venv-qds\\Scripts\\python.exe qds_preflight.py
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
TARGET_BACKEND = os.environ.get('QDS_BACKEND', 'ibm_kingston')
QUBIT = int(os.environ.get('QDS_QUBIT', '91'))


def load_token():
    path = os.environ.get(
        'IBM_TOKEN_PATH', os.path.join(HERE, 'ibm_token.json'))
    with open(path, encoding='utf-8') as f:
        return json.load(f)['apikey']


def connect():
    """Kiprobalja a modern (ibm_quantum_platform) es a legacy (ibm_quantum) csatornat."""
    from qiskit_ibm_runtime import QiskitRuntimeService
    token = load_token()
    errors = []
    for channel in ('ibm_quantum_platform', 'ibm_quantum'):
        try:
            svc = QiskitRuntimeService(channel=channel, token=token)
            print(f'[OK] csatorna: {channel}')
            return svc
        except Exception as e:  # noqa: BLE001
            errors.append(f'{channel}: {type(e).__name__}: {e}')
    print('[HIBA] egyik csatorna sem mukodik:')
    for e in errors:
        print('   -', e)
    sys.exit(2)


def main():
    svc = connect()
    print('=' * 68)

    # --- 1. Elerheto eszkozok -------------------------------------------------
    try:
        backends = list(svc.backends())
        print(f'Eszkozok szama: {len(backends)}')
        for b in backends:
            try:
                print(f'   - {b.name:<28} {b.num_qubits:>4} qubit  '
                      f'{(b.status_msg or "").strip()[:40]}')
            except Exception:  # noqa: BLE001
                print(f'   - {b.name}')
    except Exception as e:  # noqa: BLE001
        print('backend-lista hiba:', e)
        backends = []

    # --- 2. A keresett backend ------------------------------------------------
    name = None
    for cand in (TARGET_BACKEND, 'ibm_kingston', 'ibm_fez', 'ibm_marrakesh'):
        try:
            svc.backend(name=cand)
            name = cand
            break
        except Exception:  # noqa: BLE001
            continue
    if name is None:
        print(f'\n[HIBA] "{TARGET_BACKEND}" nem erheto el.')
        print('       Valasztani kell egy elerheto devot a fenti listabol.')
        sys.exit(3)

    backend = svc.backend(name=name)
    print('=' * 68)
    print(f'Backend: {name}  ({backend.num_qubits} qubit)')
    dt = getattr(backend, 'dt', None)
    print(f'dt = {dt*1e9:.4f} ns' if dt else 'dt = ismeretlen')

    # --- 3. A cel-qubit allapota ---------------------------------------------
    try:
        st = backend.status()
        print(f'Allapot: {st.status_msg.strip()}  ({st.operational})')
    except Exception:  # noqa: BLE001
        pass

    try:
        props = backend.qubit_properties(QUBIT)
        if props is None:
            print(f'Qubit {QUBIT}: NINCS tulajdonsag (nem mukodo?)')
        else:
            print(f'Qubit {QUBIT}: f={props.frequency/1e9:.4f} GHz  '
                  f'T1={props.t1*1e6:.1f} us  T2={props.t2*1e6:.1f} us')
            two_f = 1.0 / props.t2
            print(f'   1/T2 = {two_f*1e6:.3f} 1/us   '
                  f'-> a 143 us-os szimulator-felteves a valosagban '
                  f'{143.0 / (props.t2*1e6):.2f}x')
    except Exception as e:  # noqa: BLE001
        print(f'Qubit {QUBIT} adata nem elerheto: {type(e).__name__}: {e}')

    # --- 4. Kvota (ez meg MINDIG szabad) --------------------------------------
    print('-' * 68)
    for label, fn in (
        ('open plan (perc)', lambda: svc.remaining_job_minutes()),
        ('usage', lambda: svc.usage()),
        ('account', lambda: svc.my_account()),
    ):
        try:
            v = fn()
            print(f'{label}: {v}')
        except Exception as e:  # noqa: BLE001
            print(f'{label}: nem elerheto ({type(e).__name__})')

    print('=' * 68)
    print('ELOZEGES: kvota nem fogyott. Hardver job inditasahoz: --mode hardware')


if __name__ == '__main__':
    main()