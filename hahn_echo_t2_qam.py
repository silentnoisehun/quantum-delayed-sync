# -*- coding: utf-8 -*-
"""
QDS — Késleltetett Echo T₂ mérés (Szimulátor)
=============================================
A Quantum Delayed Synchronization (QDS) sinkrontérének pilot mérése.

Mérés: U -> varakozás(τ) -> U†  (echo), és U -> varakozás(τ)  (kontroll)
τ-t sweepelve, fix qubit 91, ibm_kingston.

A szkript két módban fut:
  MODE = 'simulate'  -> lokális AerSimulator (ideális + zajos), NEM hardver.
                        A szimulátor számai NEM hardvermérések!
  MODE = 'hardware'  -> igazi ibm_kingston, ez IBM kvótát használ!
"""
import json, os, sys, argparse
import numpy as np

SHOTS = 1024
BACKEND_NAME = 'ibm_kingston'
QUBIT = 91
TAUS_US = [0, 10, 25, 50, 100, 200, 400, 800]
DT_SEC = 1 / 4.5e9

# Compatibility: try transpile, fallback to basic circuit building
try:
    from qiskit import transpile
    HAS_TRANSPILE = True
except ImportError:
    HAS_TRANSPILE = False
    print("Warning: qiskit.transpile not available, using basic circuit building")

SIM_T1 = 242e-6
SIM_T2 = 143e-6
SIM_READOUT = 0.0098
SIM_1Q_ERR = 3.5e-4

np.random.seed(42)
theta = float(np.random.uniform(0, 2*np.pi))
phi = float(np.random.uniform(0, 2*np.pi))
lam = float(np.random.uniform(0, 2*np.pi))
print(f'Angles: theta={theta:.4f}, phi={phi:.4f}, lam={lam:.4f}')
print(f'Várt kontroll P(0) tau=0-nál: cos^2(theta/2) = {np.cos(theta/2)**2*100:.2f}%')

def tau_dt(tau_us, dt):
    n = int(round(tau_us * 1e-6 / dt))
    return int(16 * round(n / 16))

def build_circuits(dt, unit='dt'):
    """unit='dt'  -> a szimulator: ndt = 16-ra igazitott minta-szam
       unit='us'  -> a HARDVER: a varakozas fizikai idoban marad, a
                     transzpiler konvertalja dt-re a CEL backend dt-jevell.
                     Igy a tau-tengely nem fugg a script hardcode-olt
                     DT_SEC erteketol (ami 4.5 GHz-et feltelezett)."""
    from qiskit import QuantumCircuit
    out = []
    for tau in TAUS_US:
        dur = tau_dt(tau, dt) if unit == 'dt' else tau
        qc_e = QuantumCircuit(1)
        qc_e.u(theta, phi, lam, 0)
        qc_e.barrier()
        if dur > 0:
            qc_e.delay(dur, 0, unit=unit)
        qc_e.barrier()
        qc_e.u(theta, phi, lam, 0).inverse()
        qc_e.barrier()
        qc_e.measure_all()
        qc_c = QuantumCircuit(1)
        qc_c.u(theta, phi, lam, 0)
        qc_c.barrier()
        if dur > 0:
            qc_c.delay(dur, 0, unit=unit)
        qc_c.barrier()
        qc_c.measure_all()
        out.append((tau, dur, qc_e, qc_c))
    return out

def analytic(tau, t1, t2):
    c = np.cos(theta); s2 = np.sin(theta)**2
    e1 = np.exp(-tau / t1) if t1 else 0.0
    e2 = np.exp(-tau / t2) if t2 else 0.0
    p_echo = 0.5 + 0.5 * (e2 * s2 + e1 * c * c + c * (1 - e1))
    p_ctrl = 0.5 + 0.5 * (1 + (c - 1) * e1)
    return p_echo * 100, p_ctrl * 100

def run_simulate():
    from qiskit import transpile
    from qiskit_aer import AerSimulator
    from qiskit_aer.noise import NoiseModel, ReadoutError, depolarizing_error
    from qiskit_aer.noise.passes import RelaxationNoisePass
    sim_ideal = AerSimulator()
    dt = DT_SEC  # fix: 1/4.5e9 = 0.2222 ns
    ro = ReadoutError([[1 - SIM_READOUT, SIM_READOUT], [SIM_READOUT, 1 - SIM_READOUT]])
    nm = NoiseModel()
    nm.add_all_qubit_readout_error(ro)
    nm.add_all_qubit_quantum_error(depolarizing_error(SIM_1Q_ERR, 1), ['sx', 'x'])
    nm._custom_noise_passes.append(RelaxationNoisePass(t1s=[SIM_T1], t2s=[min(SIM_T2, 2 * SIM_T1)], dt=dt))
    sim_noisy = AerSimulator(noise_model=nm)
    print(f'dt={dt*1e9:.2f}ns T1={SIM_T1*1e6:.0f}us T2={SIM_T2*1e6:.0f}us')
    rows = []
    for tau, ndt, qc_e, qc_c in build_circuits(dt):
        res = {}
        for label, sim in (('ideal', sim_ideal), ('noisy', sim_noisy)):
            tqc_e = transpile(qc_e, sim, optimization_level=0, seed_transpiler=42)
            tqc_c = transpile(qc_c, sim, optimization_level=0, seed_transpiler=42)
            ce = sim.run(tqc_e, shots=SHOTS).result().get_counts()
            cc = sim.run(tqc_c, shots=SHOTS).result().get_counts()
            res[(label, 'e')] = ce.get('0', 0) / SHOTS * 100
            res[(label, 'c')] = cc.get('0', 0) / SHOTS * 100
        pe_th, pc_th = analytic(tau * 1e-6, SIM_T1, SIM_T2)
        print(f'tau={tau:>4}us echo={res[("noisy","e")]:.2f}% ideal={res[("ideal","e")]:.2f}% ctrl={res[("noisy","c")]:.2f}%')
        rows.append({'tau_us': tau, 'tau_dt': ndt, 'echo_noisy_pct': res[('noisy', 'e')],
                     'echo_ideal_pct': res[('ideal', 'e')], 'ctrl_noisy_pct': res[('noisy', 'c')],
                     'echo_expected_pct': pe_th, 'ctrl_expected_pct': pc_th})
    return rows

def _fit_t2_eff(taus, echo_pcts, t1):
    """Az echo görbe ILLESZTE a kalibrált T1-re -> T2_eff.

    Ez a tau-tengely ÖNVIZSGÁLATA: ha a mért T2_eff egyezik a
    kalibrált T2-vel (|axis| ~ 1), a tau skála helyes volt.
    Ha a hardver a dt-vel mas arányban számolt, T2_eff a hibás
    aránnyal lecsolgozik -> az arany a hiba foka. Nem kell újrafutni!
    """
    try:
        from scipy.optimize import curve_fit
    except ImportError:
        return None, None, None
    taus = np.asarray(taus, dtype=float) * 1e-6
    echo = np.asarray(echo_pcts, dtype=float) / 100.0
    c, s2 = np.cos(theta), np.sin(theta) ** 2

    def model(t, t2):
        e1 = np.exp(-t / t1) if t1 else np.ones_like(t)
        e2 = np.exp(-t / t2)
        return 0.5 + 0.5 * (e2 * s2 + e1 * c * c + c * (1 - e1))

    mask = taus > 0
    if mask.sum() < 3:
        return None, None, None
    try:
        popt, _ = curve_fit(model, taus[mask], echo[mask],
                            p0=[150e-6], bounds=([1e-8], [20e-3]))
        pred = model(taus[mask], popt[0]) * 100
        rms = float(np.sqrt(np.mean((echo[mask] * 100 - pred) ** 2)))
        return float(popt[0]), rms, model(taus, popt[0]) * 100
    except Exception:
        return None, None, None


def run_hardware(dry_run=False):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    try:
        from src.qam_core import QAM
    except ImportError:
        print('src/qam_core.py nem talalhato — QAM repo gyokereben kell futtatni!')
        sys.exit(1)
    from qiskit import transpile

    apikey_path = os.environ.get('IBM_TOKEN_PATH', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ibm_token.json'))
    token = json.load(open(apikey_path, encoding='utf-8')).get('apikey')
    qam = QAM(token=token, backend=BACKEND_NAME)
    backend = qam.backend

    # A CEL QUBIT VALOS T1/T2-je — NEM median! Ez az analitikus referencia.
    t1 = t2 = None
    try:
        props = backend.qubit_properties(QUBIT)
        t1, t2 = props.t1, props.t2
        print(f'Qubit {QUBIT} (kalibralt): T1={t1*1e6:.1f}us T2={t2*1e6:.1f}us')
    except Exception as e:  # noqa: BLE001
        print(f'qubit_properties nem elerheto ({e}) — median T1/T2 hasznalva')

    # A varakozas FIZIKAI IDOBAN (us) marad: igy a tau-tengely nem a
    # script hardcode-olt DT_SECjetol fugg, hanem a CEL backend dt-jet
    # konvertalja. A visszaadott ISA metadata elmondja, milyen dt-vel
    # szamolt a szerver -> osszszehasonlithato a kalibracioval.
    circuits = build_circuits(dt=None, unit='us')
    isa_jobs = []
    for tau, dur, qc_e, qc_c in circuits:
        for arm, qc in (('echo', qc_e), ('ctrl', qc_c)):
            tqc = transpile(qc, backend, optimization_level=0,
                            seed_transpiler=42, initial_layout=[QUBIT])
            isa_jobs.append((tqc, {'tau_us': tau, 'arm': arm,
                                   'delay_us': dur, 'depth': tqc.depth(),
                                   'ops': dict(tqc.count_ops())}))
    print(f'{len(isa_jobs)} circuits, {SHOTS} shots')
    for qc, meta in isa_jobs[:4]:
        for inst in qc.data:
            if inst.operation.name == 'delay':
                print(f'   pl. tau={meta["tau_us"]:>4}us {meta["arm"]}: '
                      f'delay {inst.operation.duration} '
                      f'{inst.operation.unit}')

    if dry_run:
        print('-' * 62)
        print('DRY-RUN: submit NEM tortent, kvota nem fogyott.')
        print(f'dt a targetben: {backend.target.dt} '
              f'({backend.target.dt*1e9:.4f} ns)')
        return [], {'dry_run': True, 'circuits': len(isa_jobs),
                    'target_dt': backend.target.dt,
                    't1_calibrated': t1, 't2_calibrated': t2}

    from qiskit_ibm_runtime import SamplerV2
    for qc, meta in isa_jobs:
        # a metadata a job VISSZAADOTT eredmenyeben is megjelenik, igy a
        # sorok nem kell a bekuldes sorrendjere tajekozodni utolag
        qc.metadata = {'qds': meta}
    sampler = SamplerV2(mode=backend)
    job = sampler.run([(qc,) for qc, _ in isa_jobs], shots=SHOTS)
    print(f'Job ID: {job.job_id()}  ({job.backend().name})')
    result = job.result()

    rows, isa_meta = [], None
    for i, (qc, meta) in enumerate(isa_jobs):
        pub = result[i]
        # Qiskit 2.x-ben a data bin KULCSOLVA a regiszternev ('meas'),
        # NEM '0' index -> pub.data[0] KeyError-t dob
        counts = {}
        for bin_name in pub.data.keys():
            c = pub.data[bin_name].get_counts()
            if c:
                counts = c
                break
        p0 = counts.get('0', 0) / SHOTS * 100
        meta['p0'] = p0
        meta['counts'] = dict(counts)
        rows.append(meta)
        print(f'tau={meta["tau_us"]:>4}us {meta["arm"]:>4} P(0)={p0:.2f}%')
        if isa_meta is None:
            isa_meta = pub.metadata.get('isa') if pub.metadata else None

    # Szerver oldali idozitas -> a tau-tengely onvizsgalata
    server_dt = (isa_meta or {}).get('dt')
    print('-' * 62)
    print(f'Szerver dt (ISA metadata): {server_dt}')
    if server_dt:
        print(f'   = {server_dt*1e9:.4f} ns/dt')
        print(f'   a script korábbi feltevese: {1/DT_SEC*1e9:.4f} ns/dt '
              f'(arany {server_dt/DT_SEC:.3f})')

    taus = sorted({r['tau_us'] for r in rows})
    echo = [next(r['p0'] for r in rows
                 if r['tau_us'] == t and r['arm'] == 'echo') for t in taus]
    t2_eff, rms, curve = _fit_t2_eff(taus, echo, t1)
    axis = None
    if t2_eff and t2:
        axis = t2_eff / t2
        print(f'Illesztett T2_eff = {t2_eff*1e6:.1f} us (RMS {rms:.2f}%)')
        print(f'Kalibralt T2      = {t2*1e6:.1f} us')
        print(f'TAU-TENGELY ELLENORZES: arany = {axis:.3f} '
              f'({"RENDBEN" if 0.8 < axis < 1.25 else "ELTORES — a dt-felteves rossz volt"})')
    return rows, {'server_dt': server_dt,
                  't1_calibrated': t1, 't2_calibrated': t2,
                  't2_fitted': t2_eff, 'tau_axis_ratio': axis,
                  'job_id': job.job_id()}

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='QDS Hahn Echo T2')
    parser.add_argument('--mode', choices=['simulate', 'hardware'], default='simulate')
    parser.add_argument('--dry-run', action='store_true',
                        help='hardver: minden epul de NEM kuld jobot (kvota nelkul)')
    args = parser.parse_args()
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    if args.mode == 'simulate':
        rows = run_simulate()
        with open('qam_echo_sim_results.json', 'w', encoding='utf-8') as f:
            json.dump({'mode':'simulate','noise':{'T1_us':SIM_T1*1e6,'T2_us':SIM_T2*1e6},
                        'theta':theta,'shots':SHOTS,'rows':rows}, f, indent=2)
        print('Saved: qam_echo_sim_results.json')
    else:
        rows, diag = run_hardware(dry_run=args.dry_run)
        os.makedirs('results', exist_ok=True)
        out_path = os.path.join(
            'results',
            'qam_echo_t2_dryrun.json' if args.dry_run
            else 'qam_echo_t2_results.json')
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump({'mode': 'hardware', 'backend': BACKEND_NAME,
                       'qubit': QUBIT, 'theta': theta, 'shots': SHOTS,
                       'diagnostics': diag, 'rows': rows}, f, indent=2)
        print('Saved:', out_path)