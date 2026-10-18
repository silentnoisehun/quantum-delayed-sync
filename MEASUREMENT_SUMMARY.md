# Quantum Delayed Synchronization — Measurement Summary

## 1. HARDVERES MERÉS (2026-10-18) — első valódi QPU-futás

**Job ID:** `dba0q2gc77vs738252kg` · **Backend:** `ibm_kingston` (Heron r2, 156 qubit, aktív)
**Qubit:** 91 · **Áramkör:** 16 (8 τ-érték × echo/kontroll kar) · **Shots:** 1024/áramkör
**Kvóta:** a teljes sweep **10 s** QPU-időt kötött (600 s/hó limitből 456 s maradt).

A mérés **egyben** a τ-tengely ellenőrzését is elvégezte (lásd §4).

### Eredmények

| τ (µs) | Echo mért % | Echo modell % | Δ | Kontroll mért % | Kontroll modell % | Δ |
|--------|------------|---------------|---|----------------|------------------|---|
| 0    | 99.51 | 100.00 | −0.49 | 14.45 | 14.75 | −0.29 |
| 10   | 93.46 | 95.69  | −2.23 | 21.00 | 18.04 | +2.96 |
| 25   | 87.30 | 89.68  | −2.38 | 24.22 | 22.73 | +1.49 |
| 50   | 79.69 | 80.77  | −1.08 | 32.32 | 29.97 | +2.35 |
| 100  | 61.91 | 66.33  | −4.41 | 43.75 | 42.48 | +1.27 |
| 200  | 40.92 | 46.94  | −6.03 | 60.55 | 61.19 | −0.64 |
| 400  | 29.98 | 28.13  | +1.85 | 80.08 | 82.33 | −2.25 |
| 800  | 20.90 | 17.36  | +3.54 | 92.29 | 96.34 | −4.05 |

A „modell" oszlop a mért qubit **saját T1/T2-jével** (T1 = 254,16 µs, T2 = 121,26 µs)
 számolt analitikus érték — **nem** a szimulátor median értékeivel.

### Érvényes mérésfeltételek

| # | Feltétel | Eredmény |
|---|----------|----------|
| 1 | Kontroll monoton nő | ✅ IGEN (14,45 → 92,29 %) |
| 2 | Echo monoton csökken | ✅ IGEN (99,51 → 20,90 %) |
| 3 | τ=0 echo ≈ 100 % | ✅ 99,51 % |
| 4 | τ=0 kontroll ≈ 14,75 % | ✅ 14,45 % |

### Fitelt időállandók

| Mennyiség | Kalibrált | Illesztett | Arány |
|-----------|-----------|-----------|-------|
| T1 (kontroll kar) | 254,16 ± — µs | 285,5 ± 27,6 µs | 1,123 ± 0,109 |
| T2 (echo kar) | 121,26 µs | 77,5 ± 12,9 µs | 0,639 ± 0,106 |

RMS: kontroll 2,10 %, echo 2,28 %.

## 2. A T2-ELTÉRÉS ÉRTELEME — valódi fizika, nem műszerhiba

A platform `dt = 4 ns`-ot ír (250 MHz), ami egy ~5 GHz-es qubithez fizikailag
lehetetlen, ezért **azonnal gyanús volt, hogy a τ-tengely elcsúszott**.
A döntőteszt: a **kontroll kar kizárólag T1-től függ** — ha az lenne a
probléma, a rejtett idősшалózó mindkét karat **ugyanazzal az aránnyal**
tolná el.

- kontroll arány = 1,123 ± 0,109 → **egyezik az 1,0-val** (1,1σ)
- echo arány = 0,639 ± 0,106
- a két arány különbsége 0,484 = **4,4× a hibaváltozó szórása**

**Következtetés: a τ-tengely helyes, a T2-csökkenés valós extra dekoherencia.**
Az IBM kalibrált T2-je ideális, stabil frekvenciát feltételez; a random-axis
U-delay-U-dagger visszateresi kar viszont a delay alatti frekvencia-driftet nem képes visszafókuszálni,
így a mért 77,5 µs az **echo-korlátozott** T2 — de ez egyetlen futásból
származik; a teljes kép az 5 futás átlaga (§2b).

## 2b. ISMÉTELT MÉRÉSEK (5 futás, 2026-10-18 02:03–02:21)

4 további futás (run 2–5) 75 s-os időközökkel, ugyanazon a backendon/qubiten.
Összesen 5 futás: **run 1** (visszakeresve job ID-ből) + **run 2–5** (friss).

**Kvóta:** összesen 184 s / 600 s felhasználva (416 s maradt).

### Echo kar — P(0)% átlag ± szórás (5 futás)

| τ (µs) | átlag | szórás |
|--------|-------|--------|
| 0 | 99,24 | 0,25 |
| 10 | 93,18 | 1,23 |
| 25 | 87,48 | 1,71 |
| 50 | 78,24 | 3,41 |
| 100 | 63,28 | 4,86 |
| 200 | 42,23 | 5,15 |
| 400 | 27,93 | 1,84 |
| 800 | 18,81 | 1,49 |

### Futásonkénti illesztett időállandók

| run | T₂_eff (µs) | T₂/T₂kal | T₁_eff (µs) | T₁/T₁kal |
|-----|-------------|----------|-------------|----------|
| 1 | 77,5 ± 12,9 | 0,639 | 285,5 ± 27,6 | 1,123 |
| 2 | 43,1 ± 9,0 | 0,355 | 211,6 ± 32,0 | 0,832 |
| 3 | 140,8 ± 10,7 | 1,161 | 272,6 ± 24,0 | 1,072 |
| 4 | 117,7 ± 12,5 | 0,971 | 309,3 ± 24,0 | 1,217 |
| 5 | 69,1 ± 9,0 | 0,570 | 290,3 ± 13,2 | 1,142 |

**Összesítés:**
- T₂_eff átlag = **89,6 µs**, szórás = 39,2 µs, SEM = **17,5 µs** → arány **0,74 ± 0,15**
- T₁_eff átlag = **273,8 µs**, szórás = 37,2 µs → arány **1,08 ± 0,14**
- Monotonia: **5/5** futás monoton mindkét karban
- A T₂-effektív **43–141 µs** tartományban ingadozik — ez 2,5× a futásonkénti
  illesztési hiba → **valódi időbeli drift**, nem statisztikai zaj

## 3. SZIMULÁTOROS ELŐFUTÁS (2026-10-18, 00:46)

- Zajmodell: T1 = 242 µs, T2 = 143 µs (**median** érték, NEM a 91-es qubité)
- θ = 2,353304971691044 rad, 1024 shot/áramkör

| τ (µs) | Echo mért % | Echo várt % | Kontroll mért % | Kontroll várt % |
|--------|------------|------------|----------------|----------------|
| 0 | 98.83 | 100.00 | 14.65 | 14.75 |
| 10 | 95.21 | 95.87 | 19.34 | 18.20 |
| 25 | 88.87 | 90.07 | 21.97 | 23.11 |
| 50 | 81.45 | 81.36 | 33.50 | 30.66 |
| 100 | 64.55 | 67.00 | 42.77 | 43.60 |
| 200 | 50.98 | 47.26 | 61.91 | 62.69 |
| 400 | 28.22 | 27.79 | 84.77 | 83.67 |
| 800 | 18.46 | 17.04 | 95.31 | 96.87 |

A szimulátor a hardverrel **nagyon jól** egyezik (τ=800: 18,46 % vs 20,90 %),
eltérés a valós qubit T2-jének és a valós driftnek tulajdonítható.

## 4. MIT TANULTUNK A PIPELINE-RÓL (a mérés előtti blokkolók)

1. **Környezet:** a globális Python 3.14-ben félig törölt qiskit-terra 0.x
   maradványok voltak (`qiskit/__init__.py` és `VERSION.txt` hiányzott) →
   minden import bukott. A megoldás elkülönített venv: `.venv-qds`
   (Python 3.12 + qiskit 2.6.0 + qiskit-ibm-runtime 0.50.0 + aer 0.17.2).
2. **`src/qam_core.py`** a már nem elérhető `qiskit_ibm_provider`-re épült →
   modern `QiskitRuntimeService` (`channel='ibm_quantum_platform'`, `instance='auto'`).
3. **`results/` könyvtár nem létezett** → a job lefutott, majd a mentés
   összeomlott volna. Most `os.makedirs('results', exist_ok=True)`.
4. **Qiskit 2.x adatszerkezet:** `pub.data[0]` → `KeyError`; a data bin
   kulcsa a regiszternev (`'meas'`). A javított kód a bin nevét nem feltételezi.
5. **dt:** a mérés **µs-ban** adja meg a `delay`-t, és a transzpiler konvertálja,
   így a τ-tengely nem függ a script hardcode-olt `DT_SEC`-jétől.
6. **`--dry-run` mód:** minden lépés lefut küldés nélkül — kvóta nélkül
   ellenőrizhető az áramkör, a beküldés és az eredményolvasás.

## 5. Fájlok

| Fájl | Tartalom |
|------|----------|
| `results/qam_echo_t2_results.json` | kiértékelt hardveres eredmény + nyers számok |
| `results/qam_echo_dba0q2gc77vs738252kg.json` | nyers, visszakeresett job-adatok |
| `results/qam_echo_t2_dryrun.json` | dry-run nyom (kvóta nélkül) |
| `qam_echo_sim_results.json` | szimulátoros eredmények |
| `hahn_echo_t2_qam.py` | mérőszkript (`--mode simulate\|hardware`, `--dry-run`) |
| `qds_preflight.py` / `qds_target_probe.py` | kvótamentes elővizsgálatok |
| `qds_recover_job.py` | job eredményének visszakeresése (kvóta nélkül) |
| `qds_analyze.py` | kiértékelés, T2-illesztés, τ-tengely-ellenőrzés |
| `qds_axis_arbitration.py` | kontroll-kar arbitráció (időskála vs valódi fizika) |
| `qds_replicates.py` | ismételt mérések futtatása (4+ futás, drift-időköz) |
| `qds_multirun_stats.py` | több futás statisztikája, T₂/T₁ illesztés |
| `results/raw_counts_all_runs.json` | minden futás nyers számlálói egy fájlban |
| `results/circuit_hashes.json` | sablon-hash (azonos áramkör minden futásban) |
| `results/multirun_stats.json` | kiértékelt több-futásos statisztika |