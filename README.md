# Quantum Delayed Synchronization (QDS)

> Késleltetett Echók — a memória spine szinkronizálása kvantum-állapotokkal
> **2026-10-18-től valódi IBM hardveren mérve** (`ibm_kingston`, 91-es qubit).

## Mit mérünk?

A QDS a memória spine és a kvantum-állapot koherens szinkronizációját vizsgálja.
U-delay-U-dagger visszateresi kar sweep: `U → delay(τ) → U†` (echo) kontra `U → delay(τ)` (kontroll),
8 τ-értéken (0…800 µs), fix 91-es qubiten, 1024 shot/áramkör.

A **kontroll kar nem dísz**: kizárólag T₁-től függ, ezért az időskála
referendumaként arbitrálhatja, hogy egy görbe-eltérés valódi dekoherencia-e,
vagy csupán rossz `dt`-feltevés. Lásd [`docs/QDS_CHRONICLE.md`](docs/QDS_CHRONICLE.md) FÁZIS 4.

## Fő eredmény

| mennyiség | érték |
|---|---|
| Kalibrált T₂ (91-es qubit) | 121,3 µs |
| **Mért echo-korlátozott T₂** | **77,5 µs** (több futással, lásd `results/multirun_stats.json`) |
| Kontroll karból illesztett T₁ | egyezik a kalibrálttal (1,12 ± 0,11) |

A T₂-deficit **nem mérési hiba**: az IBM kalibráció statikus frekvenciát
feltételez, a random-axis U-delay-U-dagger visszateresi kar pedig a delay alatti frekvencia-driftet nem
tudja visszafókuszálni.

## Futtatás

```bash
# 1. környezet (EGYSZER, külön venv — a globális Pythonban NE)
uv venv --clear --force --python 3.12 .venv-qds
uv pip install --python .venv-qds\Scripts\python.exe qiskit qiskit-aer qiskit-ibm-runtime

# 2. szimulátor (ingyenes)
.venv-qds\Scripts\python.exe hahn_echo_t2_qam.py --mode simulate

# 3. hardver — ELŐSZÖR MINDIG dry-run (kvótát nem fogyaszt)
.venv-qds\Scripts\python.exe hahn_echo_t2_qam.py --mode hardware --dry-run

# 4. éles hardveres mérés (IBM KVÓTÁT FOGYASZT)
.venv-qds\Scripts\python.exe hahn_echo_t2_qam.py --mode hardware

# 5. több futás, időbeli eltolással (a drift kimutatására)
.venv-qds\Scripts\python.exe qds_replicates.py --runs 4 --delay 75

# 6. kiértékelés
.venv-qds\Scripts\python.exe qds_multirun_stats.py
```

## Token

A méréshez IBM Quantum API-kulcs kell, helyi `ibm_token.json` formában:

```json
{ "apikey": "..." }
```

A fájl **nincs** a repóban (`.gitignore`), és a kulcs soha ne kerül commitba.

## Specifikáció

- Qubit: **91** (T1 = 254,16 µs, T2 = 121,26 µs a mérés pillanatában)
- Backend: `ibm_kingston` (Heron r2, 156 qubit)
- `opt_level=0`, `seed_transpiler=42`, `theta=2.3533`
- DD kikapcsolva, 1024 shot/áramkör
- A `delay` **µs-ban** van megadva → a transzpiler konvertálja dt-re

## Dokumentáció

| Fájl | Tartalom |
|---|---|
| [`MEASUREMENT_SUMMARY.md`](MEASUREMENT_SUMMARY.md) | számszerű eredmények, modellek, kvóta |
| [`docs/QDS_CHRONICLE.md`](docs/QDS_CHRONICLE.md) | a kutatás krónikája, **a hibákkal együtt** |
| [`docs/QDS_REFEREE_STATS.md`](docs/QDS_REFEREE_STATS.md) | mit bizonyít a mérés, és mit **nem** |
| [`docs/qds_measurement_log.md`](docs/qds_measurement_log.md) | mérési napló |
| [`docs/qds_raw_schema.md`](docs/qds_raw_schema.md) | nyers adatfájlok sémája |

## Adatok

```
results/
  result_runN_kingston_1024.json   egy-egy futás nyers számlálói
  raw_counts_all_runs.json         minden futás egy fájlban
  circuit_hashes.json              a sablon hash-e + módszertani megjegyzés
  multirun_stats.json              több futás statisztikája
  qam_echo_t2_results.json         kiértékelt eredmény (run 1)
```

Licenc: MIT · Zenodo: `.zenodo.json`