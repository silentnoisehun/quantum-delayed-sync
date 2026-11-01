"""QDS — ismételt hardveres mérések (a wave-quantum runN konvenciója szerint).

Miért: **egy** futásból nem lehet T2-hibasávot adni (egyetlen pont
1024 shotból ~1 %). A „hétszer megmérni ugyanazt” gyakorlat adja a hibasávot,
és kiderül, hogy a frekvencia-drift időben stabil-e — maga a QDS kérdés.

Minden futás **egy-egy külön IBM job**, így valódi időkülönbség van köztük.

Kimenet a repóban:
  ``results/result_run{N}_kingston_{shots}.json``    egy futás nyers adatai
  ``results/raw_counts_all_runs.json``               minden futás egy fájlban
  ``results/circuit_hashes.json``                    a sablon hash + megjegyzés

Használat::

    python qds_replicates.py --runs 4 --delay 75

FIGYELEM: ez **IBM kvótát fogyaszt** (futásonként 16 áramkör).
"""

import argparse
import json
import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.join(_HERE, "src")
for _p in (_HERE, _SRC):
    if os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)

from qds.circuits import build_circuits, circuit_hash  # noqa: E402
from qds.constants import (  # noqa: E402
    BACKEND_NAME,
    LAMBDA,
    PHI,
    QUBIT,
    SHOTS,
    TAUS_US,
    THETA,
)
from qds.ibm import first_counts, get_backend, sampler  # noqa: E402

RESULTS = os.path.join(_HERE, "results")

# A run1 már lefutott (job dba0q2gc77vs738252kg) → innen folytatjuk.
RUN1_JOB = "dba0q2gc77vs738252kg"
RUN1_FILE = "result_run1_kingston_1024.json"


def submit_run(backend, circuits, qubit, shots):
    """Egy futás beküldése és feldolgozása. Visszaadja a futásrekordot."""
    from qiskit import transpile

    pubs = []
    for tau, dur, qc_e, qc_c in circuits:
        for arm, qc in (("echo", qc_e), ("ctrl", qc_c)):
            tqc = transpile(qc, backend, optimization_level=0,
                            seed_transpiler=42, initial_layout=[qubit])
            tqc.metadata = {"qds": {"tau_us": tau, "arm": arm, "delay_us": dur}}
            pubs.append(tqc)
    t_submit = time.time()
    job = sampler(backend).run(pubs, shots=shots)
    start_msg = f"beküldve {job.job_id()}, várakozás a QPU-ra..."
    print(start_msg)
    res = job.result()
    elapsed = time.time() - t_submit

    points = []
    for i, qc in enumerate(pubs):
        _bin, counts = first_counts(res[i])
        md = qc.metadata["qds"]
        points.append({
            "tau_us": md["tau_us"],
            "arm": md["arm"],
            "counts": dict(counts),
            "p0_pct": counts.get("0", 0) / sum(counts.values()) * 100,
        })
    return {
        "job_id": job.job_id(),
        "submitted_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t_submit)),
        "wall_seconds": round(elapsed, 1),
        "points": points,
    }


def merge_runs(results_dir=RESULTS):
    """A ``raw_counts_all_runs.json`` újraépítése a ``result_run*.json`` fájlokból."""
    merged = {}
    run1 = os.path.join(results_dir, f"qam_echo_{RUN1_JOB}.json")
    if os.path.exists(run1):
        with open(run1, encoding="utf-8") as f:
            r1 = json.load(f)
        merged[RUN1_FILE] = {
            "run": 1,
            "job_id": RUN1_JOB,
            "backend": r1.get("backend", BACKEND_NAME),
            "qubit": r1.get("qubit", QUBIT),
            "shots": r1.get("shots", SHOTS),
            "theta": THETA,
            "note": ("az első futás; a beküldés után a parser elbukott, "
                     "az adatok job ID-ból kerültek vissza (nem futott újra)"),
            "points": [{
                "tau_us": TAUS_US[i],
                "arm": arm,
                "counts": r1["rows"][2 * i + j]["counts"],
                "p0_pct": r1["rows"][2 * i + j]["p0"],
            } for i in range(len(TAUS_US))
                for j, arm in ((0, "echo"), (1, "ctrl"))],
        }
    for fn in sorted(os.listdir(results_dir)):
        if fn.startswith("result_run") and fn != RUN1_FILE:
            with open(os.path.join(results_dir, fn), encoding="utf-8") as f:
                merged[fn] = json.load(f)
    out = os.path.join(results_dir, "raw_counts_all_runs.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(merged, f, indent=2)
        f.write("\n")
    print(f"raw_counts_all_runs.json: {len(merged)} futás → {sorted(merged)}")
    return merged


def write_circuit_hashes(circuits, results_dir=RESULTS):
    """A sablon-hash kiírása (azonos hash = azonos fizikai lánc minden futásban)."""
    payload = {
        "note": ("A hash a SABLON kanonikus utasítássorozatából készült, nem a "
                 "job visszaadott ISA-áramköréből: a Sampler a beküldött "
                 "ISA-áramköröket nem teszi lekérdezhetővé. Azonos hash = "
                 "azonos fizikai lánc minden futásban."),
        "template_sha256": circuit_hash(circuits),
        "theta": THETA, "phi": PHI, "lam": LAMBDA,
        "shots": SHOTS, "qubit": QUBIT, "backend": BACKEND_NAME,
        "taus_us": list(TAUS_US),
        "delay_unit": "us (a transzpiler konvertálja dt-re)",
    }
    out = os.path.join(results_dir, "circuit_hashes.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")
    print("circuit_hashes.json kiírva")


def main(argv=None):
    ap = argparse.ArgumentParser(description="QDS ismételt hardveres mérések")
    ap.add_argument("--runs", type=int, default=4, help="további futások száma")
    ap.add_argument("--delay", type=int, default=75,
                    help="másodperc két futás között (időbeli drift kimutatására)")
    ap.add_argument("--start", type=int, default=2, help="első futás sorszáma")
    ap.add_argument("--backend", default=BACKEND_NAME)
    ap.add_argument("--qubit", type=int, default=QUBIT)
    ap.add_argument("--shots", type=int, default=SHOTS)
    ap.add_argument("--dry-run", action="store_true",
                    help="beküldés nélkül: csak az áramkörök és a hash készül el")
    args = ap.parse_args(argv)

    os.makedirs(RESULTS, exist_ok=True)
    circuits = build_circuits(unit="us")
    chash = circuit_hash(circuits)
    print(f"sablon hash: {chash[:16]}…  (theta={THETA:.6f})")

    if args.dry_run:
        write_circuit_hashes(circuits)
        print("DRY-RUN: beküldés nem történt, kvóta nem fogyott.")
        return 0

    from qds.ibm import load_token, service

    svc = service(load_token())
    backend = get_backend(args.backend, token=load_token())
    t1 = t2 = None
    try:
        props = backend.qubit_properties(args.qubit)
        t1, t2 = props.t1, props.t2
    except Exception as exc:
        print(f"kalibráció nem elérhető: {exc}")

    made = []
    for k in range(args.start, args.start + args.runs):
        if k > args.start:
            print(f"... {args.delay} s várakozás a drift kimutatására")
            time.sleep(args.delay)
        rec = submit_run(backend, circuits, args.qubit, args.shots)
        full = {"run": k, **rec,
                "backend": args.backend, "qubit": args.qubit,
                "shots": args.shots, "theta": THETA, "phi": PHI, "lam": LAMBDA,
                "t1_calibrated_us": t1 * 1e6 if t1 else None,
                "t2_calibrated_us": t2 * 1e6 if t2 else None,
                "circuit_template_sha256": chash}
        fn = os.path.join(RESULTS, f"result_run{k}_kingston_{args.shots}.json")
        with open(fn, "w", encoding="utf-8") as f:
            json.dump(full, f, indent=2)
            f.write("\n")
        echo = {p["tau_us"]: p["p0_pct"] for p in rec["points"] if p["arm"] == "echo"}
        print(f"run{k}: {rec['job_id']} kész ({rec['wall_seconds']:.0f} s várakozás) "
              f"→ {os.path.basename(fn)}")
        print("   echo: " + " ".join(f"{t}us={echo[t]:.1f}%" for t in TAUS_US))
        made.append(k)
        try:
            u = svc.usage()
            print(f"   kvóta: {u['usage_consumed_seconds']}/"
                  f"{u['usage_limit_seconds']} s "
                  f"(maradt {u['usage_remaining_seconds']})")
        except Exception as exc:
            print(f"   kvóta-info nem elérhető: {exc}")

    merge_runs()
    write_circuit_hashes(circuits)
    print(f"kész futások: {made}")
    return 0


if __name__ == "__main__":
    from qds.cli import run

    sys.exit(run(main))
