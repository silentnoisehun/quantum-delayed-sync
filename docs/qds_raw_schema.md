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

A több futás statisztikája — a `qds_multirun_stats.py` generálja a
`raw_counts_all_runs.json`-ból (nem beégetett számokból):

```json
{
  "n_runs": 5,
  "t1_calibrated_us": 254.16, "t2_calibrated_us": 121.26,
  "job_ids": ["dba0q2gc77vs738252kg", "…"],
  "taus_us": [0, 10, 25, 50, 100, 200, 400, 800],
  "echo_p0_per_run":  {"0": [99.51, 98.83, …], "10": [93.46, …]},
  "echo_mean_pct": [99.24, 93.18, …], "echo_std_pct": [0.25, 1.23, …],
  "ctrl_p0_per_run":  {"0": [14.45, …]},
  "per_run": [
    {"run": 1, "job_id": "…", "t2_eff_us": 77.5, "t2_stderr_us": 12.9,
     "t1_eff_us": 285.5, "t1_stderr_us": 27.6,
     "t2_ratio": 0.639, "t1_ratio": 1.123}
  ],
  "t2_eff_per_run_us": [77.5, 43.1, 140.8, 117.7, 69.1],
  "t2_eff_mean_us": 89.63, "t2_eff_std_us": 39.18, "t2_eff_sem_us": 17.52,
  "t1_eff_per_run_us": [285.5, 211.6, …],
  "t1_eff_mean_us": 273.86, "t1_eff_std_us": 37.21,
  "monotonia_runs_ok": {"echo": 5, "ctrl": 5}
}
```

> A `t2_fitted_us` / `tau_axis_ratio` mezők a korábbi verzióban a
> `qam_echo_t2_results.json`-ban voltak; a τ-tengely ítélete most a kontroll
> karból jön (`tau_axis_ratio_t1`, `tau_axis_ok`), a T2-arány pedig
> `t2_ratio` néven szerepel — hogy ne lehessen összetéveszteni a kettőt.

## 5. Kiértékelt futás: `results/qam_echo_t2_results.json`

A `qds_analyze.py` kimenete: a mért és modell P(0) görbék, a két kar
illesztett időállandója, a τ-tengely ítélete, az arány-különbség
szignifikanciája, a Wilson-féle 95 %-os intervallumok és a nyers számlálók.

## Megjegyzések a nyers formához

- **Nincs `frequency_GHz`** a qubithez: a `ibm_kingston` target `qubit_properties`
  mezője `frequency=None`-t ad, ezért ezt nem tároljuk, ne is hirdessük.
- **A processor típusa**: `ibm_kingston` Heron r2 (Eagle r3 **nem**) — 156Q.
- **A `dt` nem része a sémának**, mert a platform 4 ns-os *nominális* értéket
  ad (`granularity=1`, `pulse_alignment=1`), ami nem valós pulzalidőzítés.
  A τ-tengelyt ezért a kontroll kar arbitrálja, nem a delay hossza.
- A `p0_pct` a `counts` származéka; ha kétszer számolsz, mindkettő legyen
  meg — a `counts` az elsődleges.
- A `result_run1_kingston_1024.json` **nem külön fájl**, csak a
  `raw_counts_all_runs.json` kulcsa: az első futás adatai a
  `qam_echo_dba0q2gc77vs738252kg.json`-ból (job ID-ból) állnak elő.
- A `p0` a job-visszakeresésben (`qam_echo_<JOB>.json` → `rows[].p0`) és a
  kiértékelésben is százalék; a `result_run*.json`-ban a neve `p0_pct`.
  Ugyanaz a mennyiség, két fájltípusban két néven — a `qds.data.p0_series`
  kezeli mindkettőt.