"""QDS — befejezett job eredményeinek visszakeresése (KVÓTA NÉLKÜL).

A `hahn_echo_t2_qam.py` a job lefutása **után** hibázott el az eredmények
olvasásakor (``pub.data[0]`` → ``KeyError``). A mérés nem veszett el: a job
kész, az adatok a job ID-ből újra elérhetők, ezért **nem kell** (és nem
szabad) új jobot küldeni. Ez a szkript pontosan ezt teszi.

Használat::

    python qds_recover_job.py [JOB_ID]
"""

import argparse
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.join(_HERE, "src")
if os.path.isdir(_SRC) and _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from qds.constants import BACKEND_NAME, QUBIT, SHOTS  # noqa: E402
from qds.ibm import first_counts, service  # noqa: E402

DEFAULT_JOB_ID = "dba0q2gc77vs738252kg"


def recover(job_id=DEFAULT_JOB_ID, results_dir=None, backend_name=BACKEND_NAME,
            qubit=QUBIT):
    """Letölti egy befejezett job eredményét és kiírja ``results/qam_echo_<ID>.json``-ba.

    Returns:
        dict vagy None: a mentett rekord, illetve ``None``, ha a job még nem kész.
    """
    results_dir = results_dir or os.path.join(_HERE, "results")
    job = service().job(job_id)
    print(f"Job {job_id}: status={job.status()}  backend={job.backend().name}")
    if job.status() != "DONE":
        print("A job még nem kész — nincs mit visszakeresni.")
        return None

    res = job.result()
    print(f"{len(res)} publikáció")

    rows, isa_meta = [], None
    for i, pub in enumerate(res):
        bin_name, counts = first_counts(pub)
        total = sum(counts.values())
        meta = (getattr(pub, "metadata", None) or {}).get("circuit_metadata") or {}
        qds = meta.get("qds", {})
        rows.append({
            "pub": i, "bin": bin_name, "total": total,
            "p0": counts.get("0", 0) / total * 100,
            "counts": dict(counts),
            "tau_us": qds.get("tau_us"), "arm": qds.get("arm"),
        })
        if isa_meta is None and pub.metadata:
            isa_meta = pub.metadata.get("isa")

    print("=" * 74)
    print("sor | reg  | tau(us) | kar    | P(0)%  | 0-egységek / total")
    for r in rows:
        print(f"{r['pub']:>3} | {r['bin']:<4} | {r['tau_us']!s:>7} | "
              f"{r['arm']!s:<6} | {r['p0']:>6.2f} | "
              f"{r['counts'].get('0', 0):>5} / {r['total']}")

    record = {
        "job_id": job_id,
        "backend": backend_name,
        "qubit": qubit,
        "shots": SHOTS,
        "rows": rows,
        "isa": {"dt": (isa_meta or {}).get("dt"),
                "granularity": (isa_meta or {}).get("granularity")},
    }
    os.makedirs(results_dir, exist_ok=True)
    path = os.path.join(results_dir, f"qam_echo_{job_id}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2)
        f.write("\n")
    print(f"\nmentve: {os.path.relpath(path, _HERE)}")
    print(f"ISA dt = {(isa_meta or {}).get('dt')} s, granularity = "
          f"{(isa_meta or {}).get('granularity')}")
    return record


def main(argv=None):
    parser = argparse.ArgumentParser(description="QDS job-visszakeresés")
    parser.add_argument("job_id", nargs="?", default=DEFAULT_JOB_ID)
    args = parser.parse_args(argv)
    try:
        recover(args.job_id.strip())
    except FileNotFoundError as exc:
        print(f"HIBA: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    from qds.cli import run

    sys.exit(run(main))
