"""KERESZT-REPÓ TESZT — a QDS drift-találat és a wave-quantum ⟨ZZ⟩ csatorna.

Kérdés: a QDS 5 futása szerint a 91-es qubit **fázis-koherenciája** (T2_eff)
futásról futásra ingadozik, a számított mérési zajon túl. Ha ez a drift
uralja a programokat, akkor a wave-quantum ⟨ZZ⟩ csatornájának **kontraszt A**
értékének is ingadoznia kellene futásról futásra.

FONTOS: a Pearson-r invariáns a skálára és az eltolásra. A drift a kontrasztot
(``A = max⟨ZZ⟩ − min⟨ZZ⟩``) változtatja, nem az alakot — tehát egy stabil r
**nem** cáfolja a drift-hatást, csak az A teszteli.

Ha az A **stabil**, akkor a hipotézis hamis: a drift a 91-es qubit specifikus
problémája, nem a program általános korlátja.

Áramkör: a ``wave_quantum_v3.py`` ``build_v3`` / ``run_theorem_sweep``
szerint (readout = 0, partner = 1, 13 sáv, X-bázisú kiolvasás), a run7
rögzített fizikai layoutjával.

A token a helyi ``ibm_token.json``-ból jön (nem kerül a repóba).

Használat::

    python qds_wavezz_repeat.py --runs 5 --delay 75 --dry-run   # kvóta nélkül
    python qds_wavezz_repeat.py --runs 5 --delay 75             # KVÓTÁT FOGYASZT
"""

import argparse
import json
import math
import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.join(_HERE, "src")
if os.path.isdir(_SRC) and _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from qds.constants import BACKEND_NAME  # noqa: E402
from qds.ibm import first_counts, get_backend, sampler  # noqa: E402

RESULTS = os.path.join(_HERE, "results")
N_BANDS = 13
N_QUBITS = 14
# a wave-quantum run7 rögzített layoutja (a wave_quantum_v3.py-ból)
WAVE_PHYS = [107, 106, 105, 108, 109, 110, 111, 98, 91, 92, 93, 94, 95, 99]
A_AMP = 0.5


def qds_baseline():
    """A QDS összehasonlítási alap a ``multirun_stats.json``-ból (ha van)."""
    path = os.path.join(RESULTS, "multirun_stats.json")
    try:
        with open(path, encoding="utf-8") as f:
            s = json.load(f)
        mean = s["t2_eff_mean_us"]
        sd = s["t2_eff_std_us"]
        return {"mean_us": mean, "std_us": sd, "relative_std_pct": sd / mean * 100}
    except (OSError, KeyError, TypeError, ZeroDivisionError):
        return None


def pick_layout(backend):
    """A wave-quantum layout ellenőrzése; ha kell, közeli jó párral helyettesít."""
    props = getattr(backend.target, "qubit_properties", None)
    alive = []
    if props:
        alive = [i for i, p in enumerate(props) if p is not None and p.t1 and p.t2]
    dead = [q for q in WAVE_PHYS if q not in alive]
    if not dead:
        print(f"layout: a wave-quantum layout ({WAVE_PHYS}) elérhető, használjuk.")
        return list(WAVE_PHYS)

    print(f"layout: {len(dead)} qubit a wave-layoutból nem működik itt: {dead}")
    cand = [i for i in alive if (i + 1) in alive]
    cand.sort(key=lambda i: -(props[i].t2 + props[i + 1].t2))
    pair = cand[0] if cand else alive[:2]
    rest = [q for q in alive if q not in pair][: N_QUBITS - 2]
    layout = [pair[0], pair[1], *rest]
    print(f"layout: helyettesítő pár: readout={pair[0]} partner={pair[1]}, "
          f"T2={props[pair[0]].t2 * 1e6:.0f}/{props[pair[1]].t2 * 1e6:.0f} us")
    return layout


def build_param_circuit():
    """A wave-quantum ⟨ZZ⟩ áramkör (13 sáv × 13 partner qubit)."""
    from qiskit import QuantumCircuit
    from qiskit.circuit import Parameter

    bands = [Parameter(f"b_{i}") for i in range(N_BANDS)]
    th_a, th_phi = Parameter("A_t"), Parameter("phi_t")
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
    """⟨ZZ⟩ a két qubit együttes eloszlásából."""
    p = {k: counts.get(k, 0) / shots for k in ("00", "01", "10", "11")}
    return (p["00"] + p["11"]) - (p["01"] + p["10"])


def pearson(x, y):
    n = len(x)
    mx, my = sum(x) / n, sum(y) / n
    sxy = sum((a - mx) * (b - my) for a, b in zip(x, y, strict=True))
    sxx = sum((a - mx) ** 2 for a in x)
    syy = sum((b - my) ** 2 for b in y)
    return sxy / math.sqrt(sxx * syy)


def _sd(values):
    mean = sum(values) / len(values)
    if len(values) < 2:
        return mean, 0.0
    return mean, (sum((v - mean) ** 2 for v in values) / (len(values) - 1)) ** 0.5


def main(argv=None):
    ap = argparse.ArgumentParser(description="QDS × wave-quantum ⟨ZZ⟩ kereszt-teszt")
    ap.add_argument("--runs", type=int, default=5)
    ap.add_argument("--delay", type=int, default=75)
    ap.add_argument("--shots", type=int, default=2048)
    ap.add_argument("--backend", default=BACKEND_NAME)
    ap.add_argument("--dry-run", action="store_true",
                    help="csak az áramkör felépítése, beküldés nélkül")
    ap.add_argument("--offline", action="store_true",
                    help="a meglévő results/wave_zz_repeat_run*.json adatokból "
                         "újraszámol (nem kell token, nem fogy kvóta)")
    args = ap.parse_args(argv)
    os.makedirs(RESULTS, exist_ok=True)

    if args.offline:
        return analyze_offline()

    from qiskit import transpile

    backend = get_backend(args.backend)
    layout = pick_layout(backend)
    qc, bands, th_a, th_phi = build_param_circuit()
    tqc = transpile(qc, backend=backend, initial_layout=layout,
                    optimization_level=3, seed_transpiler=42)
    print(f"transzpiler: {tqc.depth()} depth, layout={layout[:3]}…")

    if args.dry_run:
        print("DRY-RUN: beküldés nem történt, kvóta nem fogyott.")
        return 0

    theory = [math.cos(2.0 * math.pi * k / N_BANDS) for k in range(N_BANDS)]
    run_results = []
    for run in range(1, args.runs + 1):
        if run > 1:
            print(f"... {args.delay} s várakozás (az időbeli drift a cél)")
            time.sleep(args.delay)
        circuits = []
        for k in range(N_BANDS):
            ang = 2.0 * math.pi * k / N_BANDS
            binds = {th_a: 2.0 * math.asin(math.sqrt(A_AMP)), th_phi: 0.0}
            for p in bands:
                binds[p] = ang
            c = tqc.assign_parameters(binds)
            c.metadata = {"band": k}
            circuits.append(c)
        t0 = time.time()
        job = sampler(backend).run(circuits, shots=args.shots)
        print(f"run{run}: beküldve {job.job_id()} …")
        res = job.result()

        rows, meas = [], []
        for k in range(len(circuits)):
            _bin, counts = first_counts(res[k])
            zz = zz_of(counts, args.shots)
            meas.append(zz)
            rows.append({"band": k, "measured_zz": zz,
                         "theory_zz": theory[k], "counts": dict(counts)})
        r = pearson(theory, meas)
        # Kontraszt A: a Pearson-r a skálára invariáns, ezért a driftet az A
        # mutatja ki (ha a csatorna destabilizálódik, az A ingadozik).
        contrast_a = max(meas) - min(meas)
        theory_contrast = max(theory) - min(theory)
        run_results.append({
            "run": run, "job_id": job.job_id(),
            "submitted_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t0)),
            "pearson_r": r, "contrast_a": contrast_a,
            "contrast_a_theory": theory_contrast, "rows": rows,
        })
        fn = os.path.join(RESULTS, f"wave_zz_repeat_run{run}.json")
        with open(fn, "w", encoding="utf-8") as f:
            json.dump({"backend": args.backend, "shots": args.shots,
                       "layout": layout,
                       "source": "wave_quantum_v3.py build_v3",
                       "pearson_r": r, "contrast_a": contrast_a,
                       "contrast_a_theory": theory_contrast,
                       "job_id": job.job_id(), "run": run, "rows": rows},
                      f, indent=2)
            f.write("\n")
        print(f"run{run}: r = {r:.4f}  A = {contrast_a:.4f}  "
              + " ".join(f"{m:+.3f}" for m in meas))
        try:
            u = service_usage()
            print(f"   kvóta: {u['usage_consumed_seconds']}/"
                  f"{u['usage_limit_seconds']} "
                  f"(maradt {u['usage_remaining_seconds']})")
        except Exception as exc:
            print(f"   kvóta-info nem elérhető: {exc}")

    print("=" * 72)
    summary = report_summary(run_results)
    save_summary(run_results, summary)
    return 0


def report_summary(run_results):
    """A futások kiértékelése + kiírás (külön, hogy offline is hívható legyen)."""
    summary = summarize(run_results)
    print("=" * 72)
    print("PEARSON r futásonként: "
          + "  ".join(f"{v:.4f}" for v in summary["pearson_r_per_run"]))
    print(f"átlag {summary['r_mean']:.4f}  szórás {summary['r_std']:.4f}  "
          f"(relatív szórás {summary['r_relative_std_pct']:.4f} %)")
    print()
    print("KONTRASZT A (max−min ⟨ZZ⟩) futásonként: "
          + "  ".join(f"{v:.4f}" for v in summary["contrast_a_per_run"]))
    print(f"átlag {summary['contrast_a_mean']:.4f}  "
          f"szórás {summary['contrast_a_std']:.4f}  (relatív szórás "
          f"{summary['contrast_a_relative_std_pct']:.1f} %)")
    print()
    print("ÖSSZEHASONLÍTÁS a QDS T2_eff szórásával:")
    base = summary["qds_baseline"]
    if base:
        print(f"  QDS T2_eff : átlag {base['mean_us']:.1f} us, "
              f"szórás {base['std_us']:.1f} us → "
              f"{base['relative_std_pct']:.1f} % relatív")
    else:
        print("  QDS T2_eff : nincs results/multirun_stats.json "
              "(futtasd a qds_multirun_stats.py-t)")
    print(f"  wave ZZ r  : átlag {summary['r_mean']:.4f}, "
          f"szórás {summary['r_std']:.4f} → "
          f"{summary['r_relative_std_pct']:.4f} % relatív")
    print(f"  wave ZZ A  : átlag {summary['contrast_a_mean']:.4f}, "
          f"szórás {summary['contrast_a_std']:.4f} → "
          f"{summary['contrast_a_relative_std_pct']:.1f} % relatív")
    print(f"  A teoretikus: {summary['contrast_a_theory']:.4f} "
          f"(minden futásban azonos)")
    print(f"  → {summary['verdict']}")
    return summary


def save_summary(run_results, summary=None, results_dir=RESULTS):
    """A ``wave_zz_repeat_summary.json`` kiírása.

    A futás-szintű metaadatok (backend, shots, layout) is bekerülnek, hogy az
    offline újraszámolás ne veszítse el őket — korábban ez megtörtént.
    """
    summary = summary or summarize(run_results)
    first = run_results[0] if run_results else {}
    meta = {
        "backend": first.get("backend", BACKEND_NAME),
        "shots": first.get("shots"),
        "layout": first.get("layout"),
    }
    path = os.path.join(results_dir, "wave_zz_repeat_summary.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({**meta, **summary, "runs": run_results}, f, indent=2)
        f.write("\n")
    print(f"mentve: {os.path.relpath(path, _HERE)}")
    return path


def load_saved_runs(results_dir=RESULTS):
    """A korábbi futások JSON-jai (offline elemzéshez)."""
    files = sorted(
        f for f in os.listdir(results_dir)
        if f.startswith("wave_zz_repeat_run") and f.endswith(".json")
    )
    runs = []
    for fn in files:
        with open(os.path.join(results_dir, fn), encoding="utf-8") as f:
            runs.append(json.load(f))
    return runs


def analyze_offline(results_dir=RESULTS):
    """Újraszámolja az összegzést a MEGLÉVŐ futásfájlokból (kvóta nélkül).

    Ez a mód akkor hasznos, ha a kvóta elfogyott, de a nyers adatok megvannak:
    ugyanazt az elemzést adja, mint egy új futás, csak új mérés nélkül.
    """
    runs = load_saved_runs(results_dir)
    if not runs:
        print("HIBA: nincs wave_zz_repeat_run*.json a results/ könyvtárban",
              file=sys.stderr)
        return 2
    print(f"OFFLINE elemzés: {len(runs)} mentett futás "
          f"({', '.join(str(r.get('run')) for r in runs)})")
    checks = _self_checks(runs)
    for line in checks["lines"]:
        print(line)
    print("=" * 72)
    summary = report_summary(runs)
    save_summary(runs, summary, results_dir)
    return 0


def _self_checks(runs):
    """Konzisztencia-ellenőrzés: a mentett r/A egyezik-e az újraszámolttal.

    A korábbi fájlokban a ``pearson_r`` és a ``contrast_a`` is benne van; ha a
    ``rows``-ból újraszámolt érték ettől eltér, akkor a fájl kézzel (vagy más
    kóddal) módosult — ezt ki kell mondani, nem elrejteni.
    """
    lines, mismatches = ["Konzisztencia (mentett vs. rows-ból újraszámolt):"], 0
    for r in runs:
        theory = [row["theory_zz"] for row in r["rows"]]
        meas = [row["measured_zz"] for row in r["rows"]]
        r_new = pearson(theory, meas)
        a_new = max(meas) - min(meas)
        dr = abs(r_new - r.get("pearson_r", r_new))
        da = abs(a_new - r.get("contrast_a", a_new))
        ok = dr < 1e-9 and da < 1e-9
        mismatches += 0 if ok else 1
        lines.append(f"  run{r.get('run')}: r {r.get('pearson_r', float('nan')):.6f} "
                     f"({'egyezik' if dr < 1e-9 else f'ELTÉR {dr:.2e}'}), A "
                     f"{r.get('contrast_a', float('nan')):.4f} "
                     f"({'egyezik' if da < 1e-9 else f'ELTÉR {da:.2e}'})")
    lines.append(f"  → {'minden fájl konzisztens' if not mismatches else str(mismatches) + ' eltérés!'}")
    return {"lines": lines, "mismatches": mismatches}


def service_usage():
    """A kvóta-lekérdezés (külön függvényben, hogy a hiba kezelhető legyen)."""
    from qds.ibm import service
    return service().usage()


def summarize(run_results):
    """A futások összegzése — külön, hogy tesztelhető legyen (hálózat nélkül)."""
    rs = [x["pearson_r"] for x in run_results]
    a_vals = [x["contrast_a"] for x in run_results]
    r_mean, r_sd = _sd(rs)
    a_mean, a_sd = _sd(a_vals)
    baseline = qds_baseline()
    a_rel = a_sd / a_mean * 100 if a_mean else float("inf")
    r_rel = r_sd / r_mean * 100 if r_mean else float("inf")
    if a_rel > 10:
        verdict = ("AZ INGADOZÁS AZONOS NAGYSÁGRENDŰ — a kontraszt A is "
                   "ingadozik (a hipotézis TÁMASZTOTT)")
    else:
        verdict = (f"AZ r ÉS AZ A IS STABIL — a drift NEM hat a ⟨ZZ⟩ "
                   f"csatornára (r rel. szórás: {r_rel:.4f} %, A rel. szórás: "
                   f"{a_rel:.1f} %) → a hipotézis HAMIS (a drift a 91-es qubit "
                   f"specifikus)")
    return {
        "pearson_r_per_run": rs, "r_mean": r_mean, "r_std": r_sd,
        "r_relative_std_pct": r_rel,
        "contrast_a_per_run": a_vals, "contrast_a_mean": a_mean,
        "contrast_a_std": a_sd, "contrast_a_relative_std_pct": a_rel,
        "contrast_a_theory": (max(run_results[0]["rows"][i]["theory_zz"]
                                  for i in range(len(run_results[0]["rows"])))
                              - min(run_results[0]["rows"][i]["theory_zz"]
                                    for i in range(len(run_results[0]["rows"])))),
        "qds_baseline": baseline,
        # Visszafelé kompatibilitás: a korábbi verzió ezeket a kulcsokat
        # beégetve írta ki; most a results/multirun_stats.json-ból származnak.
        "qds_t2eff_mean_us": (baseline or {}).get("mean_us"),
        "qds_t2eff_std_us": (baseline or {}).get("std_us"),
        "qds_t2eff_relative_std_pct": (baseline or {}).get("relative_std_pct"),
        "verdict": verdict,
    }


if __name__ == "__main__":
    from qds.cli import run

    sys.exit(run(main))
