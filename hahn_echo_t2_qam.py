"""QDS — késleltetett echo T₂ mérés (szimulátor + IBM hardver).

Mérés: ``U → delay(τ) → U†`` (echo kar) és ``U → delay(τ)`` (kontroll kar),
8 τ-értéken, fix qubiten (alapból 91), ``ibm_kingston``.

Módok:
  ``--mode simulate``  lokális AerSimulator (ideális + zajos) — NEM hardver.
  ``--mode hardware``  igazi IBM backend, ez **IBM kvótát használ**.
  ``--dry-run``        hardver módban mindent felépít, de **nem küld** jobot.

Példák::

    python hahn_echo_t2_qam.py --mode simulate
    python hahn_echo_t2_qam.py --mode hardware --dry-run
    python hahn_echo_t2_qam.py --mode hardware --backend ibm_kingston --qubit 91

A közös konstansok és modellek a ``src/qds`` csomagban vannak; a szögek és a
τ-rács rögzítettek, mert a publikált áramkör-hash ezekből számolódik.
"""

import argparse
import json
import os
import sys

# A `src/` a repo gyökeréhez képest van; közvetlen szkriptfuttatáskor is
# elérhetővé kell tenni (telepített csomag esetén már importálható).
_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.join(_HERE, "src")
if os.path.isdir(_SRC) and _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from qds.circuits import build_circuits  # noqa: E402
from qds.constants import (  # noqa: E402
    BACKEND_NAME,
    CTRL_P0_AT_ZERO_PCT,
    DT_SEC,
    LAMBDA,
    PHI,
    QUBIT,
    SHOTS,
    SIM_1Q_ERR,
    SIM_READOUT,
    SIM_T1_US,
    SIM_T2_US,
    T1_CALIBRATED_US,
    THETA,
)
from qds.model import analytic, fit_t1, fit_t2  # noqa: E402

RESULTS_DIR = os.path.join(_HERE, "results")


def run_simulate(shots=SHOTS):
    """Ideális + zajos szimuláció (median zajmodell, NEM a 91-es qubit)."""
    from qiskit import transpile
    from qiskit_aer import AerSimulator
    from qiskit_aer.noise import NoiseModel, ReadoutError, depolarizing_error
    from qiskit_aer.noise.passes import RelaxationNoisePass

    sim_ideal = AerSimulator()
    ro = ReadoutError([[1 - SIM_READOUT, SIM_READOUT],
                       [SIM_READOUT, 1 - SIM_READOUT]])
    nm = NoiseModel()
    nm.add_all_qubit_readout_error(ro)
    nm.add_all_qubit_quantum_error(depolarizing_error(SIM_1Q_ERR, 1), ["sx", "x"])
    # A RelaxationNoisePass a target/duration nélküli utasításokat (rz, sx,
    # barrier, measure) kihagyja — ez itt szándékos: csak a delay hanylik.
    nm._custom_noise_passes.append(
        RelaxationNoisePass(t1s=[SIM_T1_US * 1e-6],
                            t2s=[min(SIM_T2_US, 2 * SIM_T1_US) * 1e-6],
                            dt=DT_SEC)
    )
    sim_noisy = AerSimulator(noise_model=nm)
    print(f"dt={DT_SEC * 1e9:.2f} ns  T1={SIM_T1_US:.0f} us  T2={SIM_T2_US:.0f} us "
          f"(MEDIAN modell — nem a {QUBIT}. qubit értéke)")

    rows = []
    for tau, ndt, qc_e, qc_c in build_circuits(dt=DT_SEC, unit="dt"):
        res = {}
        for label, sim in (("ideal", sim_ideal), ("noisy", sim_noisy)):
            for arm, qc in (("e", qc_e), ("c", qc_c)):
                tqc = transpile(qc, sim, optimization_level=0, seed_transpiler=42)
                counts = sim.run(tqc, shots=shots).result().get_counts()
                res[(label, arm)] = counts.get("0", 0) / sum(counts.values()) * 100
        pe_th, pc_th = analytic(tau, SIM_T1_US, SIM_T2_US)
        print(f"tau={tau:>4}us  echo={res[('noisy', 'e')]:.2f}%  "
              f"ideal={res[('ideal', 'e')]:.2f}%  ctrl={res[('noisy', 'c')]:.2f}%")
        rows.append({
            "tau_us": tau,
            "tau_dt": ndt,
            "echo_noisy_pct": res[("noisy", "e")],
            "echo_ideal_pct": res[("ideal", "e")],
            "ctrl_noisy_pct": res[("noisy", "c")],
            "echo_expected_pct": float(pe_th),
            "ctrl_expected_pct": float(pc_th),
        })
    return rows


def run_hardware(backend_name=BACKEND_NAME, qubit=QUBIT, shots=SHOTS,
                 dry_run=False, token=None):
    """Hardveres mérés (vagy dry-run, ami nem fogyaszt kvótát).

    Returns:
        tuple: ``(rows, diagnostics)``. Dry-run esetén ``rows`` üres.
    """
    from qiskit import transpile

    from qds.ibm import get_backend, sampler

    backend = get_backend(backend_name, token=token)

    # A CÉL QUBIT VALÓS T1/T2-je — nem a backend mediánja. Ez az analitikus
    # referencia, és a τ-tengely-arbitrációhoz is ez kell.
    t1 = t2 = None
    try:
        props = backend.qubit_properties(qubit)
        t1, t2 = props.t1, props.t2
        print(f"Qubit {qubit} (kalibrált): T1={t1 * 1e6:.1f} us  T2={t2 * 1e6:.1f} us")
    except Exception as exc:
        print(f"qubit_properties nem elérhető ({exc}) — a kalibrált T1/T2 ismeretlen")

    # A várakozás FIZIKAI IDŐBEN (µs) marad: így a τ-tengely nem a szkript
    # hardkódolt dt-feltevésétől függ, hanem a cél backend dt-jét használja a
    # transzpiler.
    circuits = build_circuits(unit="us")
    pubs = []
    for tau, dur, qc_e, qc_c in circuits:
        for arm, qc in (("echo", qc_e), ("ctrl", qc_c)):
            tqc = transpile(qc, backend, optimization_level=0,
                            seed_transpiler=42, initial_layout=[qubit])
            # A metadata a visszaadott eredményben is megjelenik, így a sorok
            # nem függnek a beküldés sorrendjétől.
            tqc.metadata = {"qds": {"tau_us": tau, "arm": arm, "delay_us": dur}}
            pubs.append(tqc)

    print(f"{len(pubs)} áramkör, {shots} shot/áramkör  ({backend_name}, qubit {qubit})")
    for qc in pubs[:2]:
        for inst in qc.data:
            if inst.operation.name == "delay":
                meta = qc.metadata["qds"]
                print(f"   pl. tau={meta['tau_us']:>4}us {meta['arm']}: "
                      f"delay {inst.operation.duration} {inst.operation.unit}")

    diag = {
        "backend": backend_name,
        "qubit": qubit,
        "shots": shots,
        "t1_calibrated_us": t1 * 1e6 if t1 else None,
        "t2_calibrated_us": t2 * 1e6 if t2 else None,
        "target_dt": _safe_dt(backend),
    }

    if dry_run:
        # Szándékosan NEM hívjuk a sampler.run()-t: a dry-run nem fogyaszt
        # kvótát, és nem is hoz létre jobot.
        print("-" * 62)
        print("DRY-RUN: beküldés NEM történt, kvóta nem fogyott.")
        print(f"dt a targetben: {diag['target_dt']} s")
        diag["dry_run"] = True
        diag["circuits"] = len(pubs)
        return [], diag

    job = sampler(backend).run(pubs, shots=shots)
    print(f"Job ID: {job.job_id()}  ({backend_name})")
    result = job.result()

    from qds.ibm import first_counts

    rows = []
    for i, qc in enumerate(pubs):
        pub = result[i]
        _bin, counts = first_counts(pub)
        total = sum(counts.values())
        meta = dict(qc.metadata["qds"])
        meta["p0"] = counts.get("0", 0) / total * 100
        meta["counts"] = dict(counts)
        rows.append(meta)
        print(f"tau={meta['tau_us']:>4}us {meta['arm']:>4}  P(0)={meta['p0']:.2f}%")

    taus = sorted({r["tau_us"] for r in rows})
    echo = [next(r["p0"] for r in rows
                 if r["tau_us"] == t and r["arm"] == "echo") for t in taus]
    ctrl = [next(r["p0"] for r in rows
                 if r["tau_us"] == t and r["arm"] == "ctrl") for t in taus]
    t2_fit = fit_t2(taus, echo, t1 * 1e6 if t1 else T1_CALIBRATED_US)
    t1_fit = fit_t1(taus, ctrl)

    print("-" * 62)
    _report_and_verdict(t1_fit, t2_fit, diag)

    diag.update({
        "job_id": job.job_id(),
        "t2_fitted_us": t2_fit["t2_us"],
        "t2_fitted_stderr_us": t2_fit["stderr_us"],
        "t1_fitted_us": t1_fit["t1_us"],
        "t1_fitted_stderr_us": t1_fit["stderr_us"],
        "fit_rms_pct": t2_fit["rms_pct"],
    })
    return rows, diag


def _report_and_verdict(t1_fit, t2_fit, diag):
    """Kiírja az illesztéseket és a τ-tengely ítéletét (a KONTROLL karból)."""
    from qds.model import axis_verdict

    t1_cal = diag.get("t1_calibrated_us")
    t2_cal = diag.get("t2_calibrated_us")
    if t1_fit["t1_us"] and t1_cal:
        r1 = t1_fit["t1_us"] / t1_cal
        print(f"T1_eff (kontroll kar) = {t1_fit['t1_us']:.1f} ± "
              f"{t1_fit['stderr_us']:.1f} us   (arány {r1:.3f}, kalibrált "
              f"{t1_cal:.1f} us)")
    else:
        r1 = None
    if t2_fit["t2_us"] and t2_cal:
        print(f"T2_eff (echo kar)     = {t2_fit['t2_us']:.1f} ± "
              f"{t2_fit['stderr_us']:.1f} us   (arány "
              f"{t2_fit['t2_us'] / t2_cal:.3f}, kalibrált {t2_cal:.1f} us)")
    verdict = axis_verdict(r1, (t1_fit["stderr_us"] / t1_cal)
                           if (t1_fit["stderr_us"] and t1_cal) else None)
    print(f"τ-TENGELY: {verdict['text']}")
    if diag.get("t2_fitted_us") and t2_cal:
        print("MEGJEGYZÉS: a T2_eff/T2_kalibrált arány NEM a τ-tengely tesztje — "
              "az a kontroll karból jön. Ez az arány az echo-korlátozott "
              "dekoherenciát méri.")


def _safe_dt(backend):
    try:
        return backend.target.dt
    except Exception:
        return None


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="QDS — késleltetett echo T2 sweep (U-delay-U† vs U-delay)")
    parser.add_argument("--mode", choices=["simulate", "hardware"], default="simulate")
    parser.add_argument("--backend", default=BACKEND_NAME,
                        help=f"IBM backend neve (alap: {BACKEND_NAME})")
    parser.add_argument("--qubit", type=int, default=QUBIT,
                        help=f"cél-qubit (alap: {QUBIT})")
    parser.add_argument("--shots", type=int, default=SHOTS,
                        help=f"shot/áramkör (alap: {SHOTS})")
    parser.add_argument("--dry-run", action="store_true",
                        help="hardver: minden felépül, de NEM küld jobot "
                             "(kvóta nélkül)")
    args = parser.parse_args(argv)

    print(f"Angles: theta={THETA:.4f}, phi={PHI:.4f}, lam={LAMBDA:.4f} "
          f"(rögzített, a publikált hash miatt)")
    print(f"Várt kontroll P(0) tau=0-nál: cos^2(theta/2) = {CTRL_P0_AT_ZERO_PCT:.2f}%")

    if args.mode == "simulate":
        if args.dry_run:
            parser.error("--dry-run csak --mode hardware mellett értelmes")
        rows = run_simulate(shots=args.shots)
        out = os.path.join(_HERE, "qam_echo_sim_results.json")
        payload = {
            "mode": "simulate",
            "noise": {"T1_us": SIM_T1_US, "T2_us": SIM_T2_US,
                      "note": "MEDIAN zajmodell — NEM a cél-qubit értékei"},
            "theta": THETA, "phi": PHI, "lam": LAMBDA,
            "shots": args.shots, "rows": rows,
        }
        with open(out, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        print(f"Mentve: {os.path.basename(out)}")
        return 0

    rows, diag = run_hardware(args.backend, args.qubit, args.shots,
                              dry_run=args.dry_run)
    os.makedirs(RESULTS_DIR, exist_ok=True)
    fname = "qam_echo_t2_dryrun.json" if args.dry_run else "qam_echo_t2_results.json"
    out = os.path.join(RESULTS_DIR, fname)
    payload = {
        "mode": "hardware",
        "backend": args.backend,
        "qubit": args.qubit,
        "theta": THETA,
        "shots": args.shots,
        "diagnostics": diag,
        "rows": rows,
    }
    with open(out, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print(f"Mentve: {os.path.relpath(out, _HERE)}")
    return 0


if __name__ == "__main__":
    from qds.cli import run

    sys.exit(run(main))
