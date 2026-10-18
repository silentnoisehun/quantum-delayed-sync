# QDS Measurement Log

> Projekt: Quantum Delayed Synchronization (QDS)
> Meres tipusa: Hahn-echo T2 sweep
> Backend: ibm_kingston

## 1. Setup

### Token Informaciok
| Token ID | Letrehozva | Leiras |
|---|---|---|
| z89zu | 2026-10-06 | IBM Quantum API key |
| jthr | 2026-10-09 | IBM Quantum API key (backup) |

### Parameter parameterek
- Qubit: 91 (initial_layout=[91])
- Backend: ibm_kingston
- opt_level=0 - a transpiler NEM torli az U*U=I-t
- seed_transpiler=42 -> theta = 2.3533 rad (kontroll tau=0: ~14.75%)
- SHOTS = 1024 / circuit (QAM konvencio)
- DD kikapcsolva (dynamical_decoupling.enable = False)

### tau sweep
| tau (us) | dt (16-aligned) | Leiras |
|---|---|---|
| 0 | 0 | Kalibra%C3%A1ci%C3%B3s alap (99%+ varhato) |
| 10 | 72 | T2 jellegu csillapodas kezdodik |
| 25 | 180 | - |
| 50 | 360 | - |
| 100 | 720 | - |
| 200 | 1440 | T2 dominál |
| 400 | 2880 | Eros csillapodas |
| 800 | 5760 | Noise floor koellen |

## 2. Szimulalator eredmeny
> Figyelem: a szimulalator MEDIAN zajmodellt hasznal (T1=242us, T2=143us).
> EZ NEM A 91-ES QUBIT MERRT ERTEKE! Hardverhez: MODE='hardware'.

| tau (us) | Echo Idealis | Echo Zajos | Echo Elvart | Kontroll Zajos | Kontroll Elvart |
|---|---|---|---|---|---|
| 0 | ~100% | 99.2% | 100% | 16.0% | ~14.75% |
| 10 | ~99% | 96.1% | 95.9% | tbd | 15.6% |
| 25 | ~98% | 89.5% | 90.1% | tbd | 17.3% |
| 50 | ~96% | 81.0% | 81.4% | tbd | 21.5% |
| 100 | ~92% | 64.6% | 67.0% | tbd | 33.0% |
| 200 | ~85% | 48.4% | 47.3% | tbd | 55.8% |
| 400 | ~73% | 28.9% | 27.8% | tbd | 78.0% |
| 800 | ~55% | 17.9% | 17.0% | tbd | 90.3% |

## 3. Ervényes merésfeltételek
1. Kontroll monoton no
2. Echo monoton csokken
3. tau=0-nal echo ~99% (ha alacsony -> kapubiga/kalibracio)

## 4. HARDVERES MERES — 2026-10-18 (első QPU-futás, kvóta: 10 s)

**Job:** `dba0q2gc77vs738252kg` · **Backend:** ibm_kingston (aktív) · **Qubit:** 91
**Áramkör:** 16 (8 tau × echo/ctrl) · **Shots:** 1024 · **Kulcs:** 456 s maradt a 600 s-os limitből.

A 91-es qubit KALIBRALT ertekei (nem median!): **T1 = 254,16 us, T2 = 121,26 us**.

| tau (us) | Echo mert % | Echo modell % | Kontroll mert % | Kontroll modell % |
|---|---|---|---|---|
| 0 | 99.51 | 100.00 | 14.45 | 14.75 |
| 10 | 93.46 | 95.69 | 21.00 | 18.04 |
| 25 | 87.30 | 89.68 | 24.22 | 22.73 |
| 50 | 79.69 | 80.77 | 32.32 | 29.97 |
| 100 | 61.91 | 66.33 | 43.75 | 42.48 |
| 200 | 40.92 | 46.94 | 60.55 | 61.19 |
| 400 | 29.98 | 28.13 | 80.08 | 82.33 |
| 800 | 20.90 | 17.36 | 92.29 | 96.34 |

### Merésfeltételek: mind IGEN
Kontroll monoton no · Echo monoton csokken · tau=0 echo 99.51% · tau=0 kontroll 14.45%

### A T2-eltérés nem hiba, hanem eredmény
A platform `dt = 4 ns`-ot ir (250 MHz) — fizikailag lehetetlen 5 GHz-es qubithez,
igy gyanus volt az elcsuszott tau-tengely. **A kontroll kar arbitralt:** csak T1-tol
fugg, igy egy rejtett idoskalaszor mindket karat AZONOS arannyal tolna el.
- T1 arany = 1.123 ± 0.109 (egyezik az 1.0-val)
- T2 arany = 0.639 ± 0.106
- kulonbseg 0.484 = 4.4× a szoras → **nem idoskala, valos extra dekoherencia**

**T2_eff = 77,5 ± 12,9 us** az echo-korlatozott T2: a random-axis Hahn-echo nem
tudja visszafokuszalni a delay alatti frekvencia-driftet, amit az IBM kalibralt
T2-je idealisnak tekint. Ez a QDS pilot fo eredmenye.

Reszletek: `MEASUREMENT_SUMMARY.md` §1-2
