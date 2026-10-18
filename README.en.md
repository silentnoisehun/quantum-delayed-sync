# Quantum Delayed Synchronization (QDS)

> Delayed echoes — synchronizing the memory spine with quantum states
> **Measured on real IBM hardware since 2026-10-18** (`ibm_kingston`, qubit 91).

## What do we measure?

QDS investigates coherent synchronization between the memory spine and quantum
state. U-delay-U-dagger visszateresi kar sweep: `U → delay(τ) → U†` (echo) vs `U → delay(τ)` (control),
across 8 τ values (0…800 µs), fixed qubit 91, 1024 shots/circuit.

The **control arm is not decoration**: it depends on T₁ alone, which makes it
the *arbitrator* for whether a curve deviation is real decoherence or merely a
wrong `dt` assumption. See [`docs/QDS_CHRONICLE.md`](docs/QDS_CHRONICLE.md), Phase 4.

## Main result

| quantity | value |
|---|---|
| Calibrated T₂ (qubit 91) | 121.3 µs |
| **Measured echo-limited T₂** | **77.5 µs** (multi-run, see `results/multirun_stats.json`) |
| T₁ fitted from the control arm | consistent with calibration (1.12 ± 0.11) |

The T₂ deficit is **not a measurement error**: IBM's calibration assumes a static
frequency, while a random-axis Hahn echo cannot refocus frequency drift during
the delay.

## Running

```bash
# 1. environment (ONCE, separate venv — never in the global Python)
uv venv --clear --force --python 3.12 .venv-qds
uv pip install --python .venv-qds\Scripts\python.exe qiskit qiskit-aer qiskit-ibm-runtime

# 2. simulator (free)
.venv-qds\Scripts\python.exe hahn_echo_t2_qam.py --mode simulate

# 3. hardware — ALWAYS dry-run first (consumes no quota)
.venv-qds\Scripts\python.exe hahn_echo_t2_qam.py --mode hardware --dry-run

# 4. live hardware measurement (CONSUMES IBM QUOTA)
.venv-qds\Scripts\python.exe hahn_echo_t2_qam.py --mode hardware

# 5. repeated runs, time-spaced (to expose drift)
.venv-qds\Scripts\python.exe qds_replicates.py --runs 4 --delay 75

# 6. multi-run statistics
.venv-qds\Scripts\python.exe qds_multirun_stats.py
```

## Token

Hardware runs need an IBM Quantum API key in a local `ibm_token.json`:

```json
{ "apikey": "..." }
```

That file is **not** in the repo (`.gitignore`), and the key must never be committed.

## Specification

- Qubit: **91** (T1 = 254.16 µs, T2 = 121.26 µs at measurement time)
- Backend: `ibm_kingston` (Heron r2, 156 qubits)
- `opt_level=0`, `seed_transpiler=42`, `theta=2.3533`
- DD disabled, 1024 shots/circuit
- `delay` is given in **µs** → the transpiler converts to dt

## Documentation

| File | Content |
|---|---|
| [`MEASUREMENT_SUMMARY.md`](MEASUREMENT_SUMMARY.md) | numeric results, models, quota |
| [`docs/QDS_CHRONICLE.md`](docs/QDS_CHRONICLE.md) | research chronicle, **including the mistakes** |
| [`docs/QDS_REFEREE_STATS.md`](docs/QDS_REFEREE_STATS.md) | what the measurement proves — and what it does **not** |
| [`docs/qds_measurement_log.md`](docs/qds_measurement_log.md) | measurement log |
| [`docs/qds_raw_schema.md`](docs/qds_raw_schema.md) | raw data file schema |

## Data

```
results/
  result_runN_kingston_1024.json   raw counts per run
  raw_counts_all_runs.json         all runs in one file
  circuit_hashes.json              template hash + methodological note
  multirun_stats.json              multi-run statistics
  qam_echo_t2_results.json         evaluated result (run 1)
```

License: MIT · Zenodo: `.zenodo.json`