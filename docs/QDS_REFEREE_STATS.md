# BÍRÁLÓI STATISZTIKA — mit bizonyít az 5 futás, és mit nem
**2026-10-18 · A wave-quantum REFEREE_STATS.md mintájára**

---

## A KRITIKA — amit előre elfogadunk

> „Öt futás, egyetlen qubiten, egyetlen backendon, egyetlen napon — ez
> nem új fizika, és nem bizonyít semmit a Hope architektúráról."

**A kritika helytálló.** Alább pontosan leírjuk, mi a védhető állítás.

## Mit bizonyít az 5 futás

| # | Állítás | Bizonyíték |
|---|---------|-----------|
| 1 | **A pipeline működik**: token, venv, áramkör, beküldés, eredmény-parsol, T₂-illesztés | 5/5 futás sikeres, 0 elveszett adat |
| 2 | **A mérés érvényes**: kontroll monoton nő, echo monoton csökken, τ=0 értékek egyeznek | 5/5 mindkét monotonia-teszt IGEN |
| 3 | **A τ-tengely helyes**: a kontroll kar T₁-aránya 1,077 (5 futás átlaga) / 1,123 ± 0,109 (run 1, a hibán belül) | A T₁- és T₂-arány különbsége run 1-ben 0,484 = **3,2σ** → nem időskála |
| 4 | **Az echo-korlátozott T₂ < kalibrált T₂**: 89,6 ± 17,5 µs vs 121,3 µs | 5 futás átlaga, SEM = 17,5 µs, az eltérés 31,6 µs = **1,81 SEM** (p ≈ 0,07, egymintás t) — *irányadó, nem döntő* |
| 5 | **A T₂-effektív futásról futásra ingadozik**: szórás 39,2 µs, tartomány 43,1–140,8 µs | Heterogenitás-χ² = 60,9, df = 4, p ≈ 2·10⁻¹² → nem magyarázható a futásonkénti illesztési hibával (a szórás 3,6× az átlagos hibának) |

## Mit NEM bizonyít

| # | Nem bizonyított állítás | Miért nem |
|---|------------------------|-----------|
| 1 | **Új fizika** | A U-delay-U-dagger visszateresi kar T₂ < kalibrált T₂ **jól ismert jelenség**; a random-axis echo érzékenyebb a driftre, mint a Ramsey, de ez nem újdonság |
| 2 | **A Hope architektúra működik** | A mérés konzisztens a relációs információ-felfogással, de NEM bizonyíték rá — motiváció, nem igazolás |
| 3 | **A 91-es qubit rosszabb, mint a többi** | Egyetlen qubitről nincs összehasonlítás; a 91-es a 86/154-ik a T₂-rangsorban |
| 4 | **A drift oka ismert** | A frekvencia-drift forrása (hőmérséklet, TLS, kozmikus sugárzás) ebből a mérésből nem azonosítható |
| 5 | **A T₂-effektív stabil** | Az 5 futás **pont azt mutatja**, hogy nem az — a 39 µs szórás az eredmény, nem a hiba |

## Számok

```
Backend:    ibm_kingston (Heron r2, 156 qubit)
Qubit:      91
Futások:    5 (run 1 visszakeresve job ID-ből)
Kvóta:      184 s / 600 s felhasználva (416 s maradt)
Shots:      1024 / áramkör
Áramkörök:  16 / futás (8 τ × echo/ctrl)

Kalibrált:  T₁ = 254,16 µs   T₂ = 121,26 µs
Mért átlag: T₁_eff = 273,8 ± 37,2 µs (arány 1,08)
            T₂_eff = 89,6 ± 39,2 µs (szórás), SEM = 17,5 µs (arány 0,74 ± 0,15)
            χ²(T₂) = 60,9 (df=4, p≈2·10⁻¹²)   χ²(T₁) = 7,7 (df=4, p=0,10)
```


## Robusztusság-ellenőrzések (2026-11-01, `qds_robustness.py`)

Új mérés nélkül, a meglévő 5 futás adataiból. Cél: kiderüljön, mennyire
függ az eredmény az illesztés módszerétől.

### 1. A futás-átlagolt görbe és a futásonkénti illesztések átlaga NEM ugyanaz

| becslés | T₂ (µs) |
|---|---|
| futásonkénti T₂_eff **átlaga** (a fő, publikált szám) | **89,6 ± 17,5** (SEM) |
| a **futás-átlagolt görbére** illesztve | **79,3 ± 6,8** |
| ugyanaz bootstrap 95 % CI-vel (2000 ismétlés) | 66,9–89,8 |

A két becslés **nem ugyanaz a mennyiség**: az átlagolandó T₂_eff nemlineáris
függvénye a pontoknak, ezért a görbe-átlagolás után illesztett érték
rendszerint alacsonyabb. A publikált **89,6 µs a futásonkénti becslések
átlaga**; a 79,3 µs a „tipikus görbére” vonatkozó érték. A futások közti
ingadozás (σ = 39,2 µs) nagyobb, mint a kettő közti különbség (10,4 µs), tehát
egyik becslés sem cáfolja a másikat.

### 2. A hibasáv nem alulbecsült

| ellenőrzés | eredmény |
|---|---|
| bootstrap / görbe-illesztés hibaaránya | **0,87×** (összhangban, nem szélesebb) |
| súlyozott (shot-noise 1/σ²) vs. súlyozatlan T₂ | −2,9 % (76,9 vs. 79,3 µs) |
| τ-tartomány érzékenysége | ≤400 µs: 79,3 · ≤200 µs: 79,1 · ≥25 µs: 80,8 · ≤100 µs: 83,3 µs |

A τ-tartományra való érzékenység **±5 %**-on belül van: az eredményt nem a
hosszú τ-k (vagy a τ=0 pont) uralják.

### 3. A T₁-ből származó τ-tengely állítás robusztus

A futás-átlagolt kontroll görbére illesztett T₁ = 276,9 ± 23,1 µs,
bootstrap 95 % CI **241,4–294,9 µs** — ez **tartalmazza** a kalibrált
254,2 µs-ot, és a T₂-oldali bootstrap (66,9–89,8 µs) **nem** tartalmazza a
kalibrált 121,3 µs-ot. A τ-tengely vs. valódi dekoherencia szétválasztása tehát
nem az illesztési módszer műterméke.

> **Korlát:** a bootstrap a reziduálisok újramintázásán alapul, ami feltételezi,
> hogy a modell helyes és a hibák függetlenek. A futások közti drift
> (σ = 39,2 µs) **nagyobb**, mint a futáson belüli illesztési hiba, ezért a
> futásonkénti hibasávok a *futáson belüli* bizonytalanságot írják le, nem a
> driftét — utóbbit a χ²-teszt méri (§ fent).

## Összefoglalás egy mondatban

> Az 5 futás azt bizonyítja, hogy a QDS pipeline éles IBM hardveren működik,
> és a random-axis U-delay-U† visszatérési kar T₂-je **kisebb és futásról futásra ingadozik**,
> mint a kalibrált T₂ — de a jelenség önmagában nem új, és a Hope
> architektúráról semmit nem mond.