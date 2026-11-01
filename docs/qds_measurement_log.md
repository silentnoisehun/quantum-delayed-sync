# QDS mérési napló

> Projekt: Quantum Delayed Synchronization (QDS)
> Mérés típusa: U-delay-U† (Hahn-echo) T2 sweep
> Backend: `ibm_kingston` · Qubit: 91

## 1. Beállítások

### Tokenek
| Token azonosító | Létrehozva | Leírás |
|---|---|---|
| z89zu | 2026-10-06 | IBM Quantum API-kulcs |
| jthr | 2026-10-09 | IBM Quantum API-kulcs (tartalék) |

> Csak az azonosítók: maga a kulcs soha nem kerül a repóba (`.gitignore`).

### Mérési paraméterek
- Qubit: 91 (`initial_layout=[91]`)
- Backend: `ibm_kingston`
- `opt_level=0` — a transzpiler NEM törli az U·U† = I azonosságot
- `seed_transpiler=42`; a szögek rögzítettek: θ = 2,3533 rad (kontroll τ=0: ~14,75 %)
- `SHOTS = 1024` / áramkör (QAM konvenció)
- DD kikapcsolva

### τ-sweep

| τ (µs) | szimulátor dt (16-ra igazítva) | megjegyzés |
|---|---|---|
| 0 | 0 | kalibrációs alap (99 %+ várható) |
| 10 | 44992 | a T2-jellegű csillapodás elkezdődik |
| 25 | 112496 | — |
| 50 | 224992 | — |
| 100 | 449984 | — |
| 200 | 899968 | T2 dominál |
| 400 | 1799968 | erős csillapodás |
| 800 | 3599968 | a zajszint közelében |

> A táblázat a **szimulátor** 4,5 GHz-es dt-feltevésével számolt értékeket
> mutatja. A **hardveres** áramkör a τ-t fizikai időben (µs) adja meg, és a
> transzpiler konvertálja a cél backend dt-jével (4 ns) — a kettő nem ugyanaz
> a szám. A szimulátor `tau_dt` mezője a `RelaxationNoisePass` bemenete.

## 2. Szimulátoros eredmény (2026-10-18, 00:46)

> Figyelem: a szimulátor **MEDIAN** zajmodellt használ (T1 = 242 µs, T2 = 143 µs).
> **EZ NEM A 91-ES QUBIT MÉRT ÉRTÉKE!** Hardverhez: `--mode hardware`.

| τ (µs) | Echo ideális | Echo zajos | Echo elvárt | Kontroll zajos | Kontroll elvárt |
|---|---|---|---|---|---|
| 0 | 100.00 | 98.83 | 100.00 | 14.65 | 14.75 |
| 10 | 100.00 | 95.21 | 95.87 | 19.34 | 18.20 |
| 25 | 100.00 | 88.87 | 90.07 | 21.97 | 23.11 |
| 50 | 100.00 | 81.45 | 81.36 | 33.50 | 30.66 |
| 100 | 100.00 | 64.55 | 67.00 | 42.77 | 43.60 |
| 200 | 100.00 | 50.98 | 47.26 | 61.91 | 62.69 |
| 400 | 100.00 | 28.22 | 27.79 | 84.77 | 83.67 |
| 800 | 100.00 | 18.46 | 17.04 | 95.31 | 96.87 |

## 3. Érvényes mérésfeltételek

1. Kontroll monoton nő
2. Echo monoton csökken
3. τ=0-nál az echo ≈ 99 % (ha alacsony → kapuhiba/kalibráció)
4. τ=0-nál a kontroll ≈ cos²(θ/2) = 14,75 %

## 4. HARDVERES MÉRÉS — 2026-10-18 (első QPU-futás, kvóta: 10 s)

**Job:** `dba0q2gc77vs738252kg` · **Backend:** ibm_kingston (aktív) · **Qubit:** 91
**Áramkör:** 16 (8 τ × echo/kontroll) · **Shots:** 1024 · **Kvóta:** 10 s felhasználva, 456 s maradt a 600 s-os limitből.

A 91-es qubit KALIBRÁLT értékei (nem medián!): **T1 = 254,16 µs, T2 = 121,26 µs**.

| τ (µs) | Echo mért % | Echo modell % | Kontroll mért % | Kontroll modell % |
|---|---|---|---|---|
| 0 | 99.51 | 100.00 | 14.45 | 14.75 |
| 10 | 93.46 | 95.69 | 21.00 | 18.04 |
| 25 | 87.30 | 89.68 | 24.22 | 22.73 |
| 50 | 79.69 | 80.77 | 32.32 | 29.97 |
| 100 | 61.91 | 66.33 | 43.75 | 42.48 |
| 200 | 40.92 | 46.94 | 60.55 | 61.19 |
| 400 | 29.98 | 28.13 | 80.08 | 82.33 |
| 800 | 20.90 | 17.36 | 92.29 | 96.34 |

### Mérésfeltételek: mind IGEN
Kontroll monoton nő · Echo monoton csökken · τ=0 echo 99,51 % · τ=0 kontroll 14,45 %

### A T2-eltérés nem hiba, hanem eredmény
A platform `dt = 4 ns`-ot ír (250 MHz) — fizikailag lehetetlen 5 GHz-es qubithez,
így gyanús volt az elcsúszott τ-tengely. **A kontroll kar arbitralt:** csak T1-től
függ, így egy rejtett időskálázó mindkét kart AZONOS aránnyal tolná el.
- T1 arány = 1,123 ± 0,109 (egyezik az 1,0-val)
- T2 arány = 0,639 ± 0,106
- különbség 0,484 = 3,2σ → **nem időskála, valós extra dekoherencia**

**T2_eff = 77,5 ± 12,9 µs** az echo-korlátozott T2: a random-axis U-delay-U† visszatérési kar nem
tudja visszafókuszálni a delay alatti frekvencia-driftet, amit az IBM kalibrált
T2-je ideálisnak tekint. Ez a QDS pilot fő eredménye — a teljes kép az 5 futás
átlaga (89,6 µs), lásd `results/multirun_stats.json` és `MEASUREMENT_SUMMARY.md` §2b.

Részletek: `MEASUREMENT_SUMMARY.md` §1–2
