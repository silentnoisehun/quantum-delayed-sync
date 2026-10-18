# Nyers adatfájlok sémája — QDS

> A ténylegesen előállított fájlok sémája. A korábbi `measurement_raw/audit_qds_echo_*.json`
> leírás **soha nem volt implementálva**; a formátum alább a valós kimenet.

## 1. Egy futás: `results/result_run{N}_kingston_{shots}.json`

Az egyedi futások nyers számlálói — **ez a kanonikus nyers forma**.

```json
{
  "run": 2,
  "job_id": "dba0u8hgv2cc73e66p10",
  "backend": "ibm_kingston",
  "qubit": 91,
  "shots": 1024,
  "theta": 2.353304971691044,
  "phi": 5.97353...,
  "lam": 4.59931...,
  "submitted_utc": "2026-10-18T00:13:14Z",
  "wall_seconds": 52.4,
  "t1_calibrated_us": 254.1627621299776,
  "t2_calibrated_us": 121.25600306875533,
  "circuit_template_sha256": "…",
  "points": [
    {
      "tau_us": 0,
      "arm": "echo",
      "counts": {"0": 1019, "1": 5},
      "p0_pct": 99.51171875
    }
    // … 8 τ × 2 kar = 16 pont, a beküldési sorrendben …
  ]
}
```

**Fontos:** a `t1_calibrated_us` / `t2_calibrated_us` a mérés **pillanatában**
kérdezett le kalibráció, nem konstans. A modell mindig ehhez igazodik.

## 2. Összesített: `results/raw_counts_all_runs.json`

A top-level kulcsok a **fájlnevek** (a `wave-quantum` konvenciója szerint),
a `result_run1_kingston_1024.json` kulcs kézi beemeléssel kerül bele,
mert az első futás adatai külön úton (job ID-ből) jöttek vissza:

```json
{
  "result_run1_kingston_1024.json": { "…": "…" },
  "result_run2_kingston_1024.json": { "…": "…" },
  "result_run3_kingston_1024.json": { "…": "…" }
}
```

## 3. Áramkör-hash: `results/circuit_hashes.json`

```json
{
  "note": "A hash a SABLON kanonikus utasítás-sorozatából készült, nem a job
           visszaadott ISA-áramköréből: a SamplerV2 a beküldött ISA-áramköröket
           nem teszi lekérdezhetővé.",
  "template_sha256": "…",
  "theta": …, "phi": …, "lam": …,
  "shots": 1024, "qubit": 91, "backend": "ibm_kingston",
  "taus_us": [0, 10, 25, 50, 100, 200, 400, 800],
  "delay_unit": "us (a transzpiler konvertálja dt-re)"
}
```

Azonos hash minden futásban ⇒ azonos fizikai lánc épült.

## 4. Kiértékelés: `results/multirun_stats.json`

A több futás statisztikája: futásonkénti P(0), átlag ± szórás, illesztett
T₂/T₁ futásonként, monotoniateszt futásonként.

## Megjegyzések a nyers formához

- **Nincs `frequency_GHz`** a qubithez: a `ibm_kingston` target `qubit_properties`
  mezője `frequency=None`-t ad, ezért ezt nem tároljuk, ne is hirdessük.
- **A processor típusa**: `ibm_kingston` Heron r2 (Eagle r3 **nem**) — 156Q.
- **A `dt` nem része a sémának**, mert a platform 4 ns-os *nominális* értéket
  ad (`granularity=1`, `pulse_alignment=1`), ami nem valós pulzalidőzítés.
  A τ-tengelyt ezért a kontroll kar arbitrálja, nem a delay hossza.
- A `p0_pct` a `counts` származéka; ha kétszer számolsz, mindkettő legyen
  meg — a `counts` az elsődleges.