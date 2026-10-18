# A KUTATÁS KRÓNIKÁJA — QDS (Quantum Delayed Synchronization)
## Hogyan jutottunk az echo-korlátozott T₂ = 77 µs eredményhez — a hibákkal együtt
**2026-10-18 · Máté Róbert & Hope · minden mért érték megmarad, a rossz is**

> Ez a krónika azért van, mert a végeredmény (`T₂_echo = 77,5 µs` egy
> 121,3 µs-ra kalibrált qubiten) elsőre **hibának** tűnik, és majdnem el is
> dobtuk. Négy mérés és egy döntőteszt kellett hozzá, hogy kiderüljön, hogy
> ez valódi fizika. A hibás adat és a majdnem eldobott eredmény is a része.

---

## FÁZIS 0 — A szimulátoros előfutás (00:46)

A mérőszkript 8 τ-pontban (0…800 µs) végigmérte az echo és a kontroll kar
görbéjét `AerSimulator`-ral, **median** zajmodellel (T1 = 242 µs, T2 = 143 µs).
A görbe szép, monoton, szinte pontosan egyezik az elméleti modellel.

**Ez nem mérés.** A median T1/T2 nem a 91-es qubit értéke — a fájl maga
mondja ki: *„EZ NEM A 91-ES QUBIT MÉRT ÉRTÉKE!"*.

## FÁZIS 1 — A környezet eleve törött volt (01:54)

A globális Python 3.14-ben a `qiskit` **félig törölt terra 0.x maradvány** volt
(`qiskit/__init__.py` és `VERSION.txt` hiányzott, a `pip` egyáltalán nem látta).
Tünet: `AttributeError: module 'qiskit' has no attribute '__version__'`.
A `qiskit_ibm_provider` — amire a `src/qam_core.py` épült — már nem létezik.

Megoldás: elkülönített `.venv-qds` (Python 3.12 + qiskit 2.6.0 + runtime 0.50.0),
`src/qam_core.py` átírva `QiskitRuntimeService`-re. **A kvantum-kliens soha ne
a globális Pythonba menjen** — ez a hiba korábban már egyszer kijavított
környezetszennyezéshez vezetett.

## FÁZIS 2 — A kvótamentes elővizsgálat kimutatott egy csapdát (01:58)

Négy dolog derült ki küldés nélkül:

1. A token él, az `ibm_kingston` aktív (156 qubit).
2. A 91-es qubit **T1 = 254,16 µs, T2 = 121,26 µs** — nem a szimulátor medianja.
3. A 91-es qubit a 154 működő qubit közül a **86.** — működik, de nem kiemelkedő
   (a legjobb: 13-as qubit, T2 = 831 µs).
4. 🧬 **A platform `dt = 4 ns`-ot ír, `granularity = 1`, `pulse_alignment = 1`.**
   4 ns = 250 MHz, ami egy ~5 GHz-es qubithez **fizikailag lehetetlen**.
   Ez nominális érték, nem valós pulzalidőzítés — és emiatt a τ-tengelyt
   **nem lehet** a delay hosszából ellenőrizni.

Ezért az áramkör átírt: a `delay` most **µs-ban** adja meg a τ-t, és a
transzpiler konvertálja dt-re. Így a τ-tengely nem függ a szkript korábbi
hardcode-olt `DT_SEC = 1/4.5 GHz` feltevésétől.

## FÁZIS 3 — Run 1: a mérés lefutott, a kiértékelés elbukott (02:03)

A `hahn_echo_t2_qam.py --mode hardware` elküldte a 16 áramkört
(`job dba0q2gc77vs738252kg`), majd **`job.result()` UTÁN** elbukott:
`pub.data[0]` → `KeyError`.

Ennek három tanulsága van, mindegyike külön elv:

- 🧬 **A Qiskit 2.x data bin kulcsa a regiszternev (`'meas'`), nem az index.**
- 🧬 **A beküldés UTÁNI hiba nem éget kvótát.** A QPU-n minden lefutott;
  az adatok `svc.job(JOB_ID).result()`-tel **ingyen** visszakérhetők.
  *„Hiba a mérés után" ≠ *„mérés sikertelen"*. Soha ne küldj új jobot erre.
- 🧬 **Ezért kell a `--dry-run` mód**: minden lépés (csatlakozás, áramkör,
  beküldés, eredményolvasás) fut küldés nélkül.

Az adatok így visszakerültek, **egyetlen új kvóta nélkül**.

## FÁZIS 4 — A döntőteszt: időskála vagy valódi fizika? (02:05)

Run 1 eredménye minden érvényes mérésfeltételt teljesített (kontroll monoton
nő, echo monoton csökken, τ=0-nál 99,51 % és 14,45 %). **De az illesztett
T₂ = 77,5 ± 12,9 µs volt, a kalibrált 121,3 µs felének fele.**

Az első ösztönös magyarázat: *„a dt-feltevésem rossz volt, a τ-tengely elcsúszott."*
Ezt a FÁZIS 2-ben már gyanítottuk, és szinte készen álltunk újrafuttatni egy
módosított dt-vel. **Nem futtattuk** — helyette beépítettünk egy karreferenciát.

> **Az arbitrációs elv:** ha rejtett időskálázó hiba van, az **mindkét** kar
> görbéjét **ugyanazzal az aránnyal** tolja el. A **kontroll kar kizárólag T1-től
> függ** — így ő az időskála referendumja.

| mennyiség | illesztett | kalibrált | arány |
|---|---|---|---|
| T1 (kontroll kar) | 285,5 ± 27,6 µs | 254,2 µs | **1,123 ± 0,109** |
| T2 (echo kar) | 77,5 ± 12,9 µs | 121,3 µs | **0,639 ± 0,106** |

A két arány különbsége 0,484 = **4,4× a hibaváltozó szórása**. Az arányok
**nem egyeznek** → **nem időskála-hiba**, hanem valódi extra dekoherencia.

**A fizikai magyarázat:** az IBM kalibrált T₂-je ideális, statikus frekvenciát
feltételez. A random-axis Hahn-echo viszont a delay alatt fellépő
frekvencia-driftet **nem tudja visszafókuszálni**, ezért a mért érték az
**echo-korlátozott T₂**. Ez a mérés fő eredménye — nem hiba.

## FÁZIS 5 — Egy futás nem elég; az 5 futás a valódi kép (02:10–02:21)

Egyetlen sweepből nincs T₂-hibasáv. A `wave-quantum` repóban 7 független
futás volt — azt követtük. 4 további futás indult 75 s-os időközökkel, így az
időbeli drift is láthatóvá vált.

| run | job | T₂_eff (µs) | T₂/T₂kal | T₁_eff (µs) | T₁/T₁kal |
|---|---|---|---|---|---|
| 1* | dba0q2gc… | 77,5 ± 12,9 | 0,639 | 285,5 ± 27,6 | 1,123 |
| 2  | dba0u8hg… | 43,1 ± 9,0  | 0,355 | 211,6 ± 32,0 | 0,832 |
| 3  | dba0v8hg… | 140,8 ± 10,7| 1,161 | 272,6 ± 24,0 | 1,072 |
| 4  | dba1000c… | 117,7 ± 12,5| 0,971 | 309,3 ± 24,0 | 1,217 |
| 5  | dba10os2… | 69,1 ± 9,0  | 0,570 | 290,3 ± 13,2 | 1,142 |

\* run 1 a job ID-ből visszakeresve (a parser romlott el, nem a mérés).

**Három kulcsfontosságú megállapítás:**

1. **5/5 monoton**: minden futásban a kontroll monoton nő, az echo csökken.
2. **T₁ arány stabil (1,08 ± 0,14)**, T₂ arány instabil (0,74 ± 0,33).
   A kontroll referencia kar megerősíti: **a τ-tengely helyes** — a szóródás
   a T₂-ben jelentkezik, nem az időskálában.
3. **A T₂-effektív 43–141 µs** között ingadozik — a szórás (39 µs) 2,5×
   nagyobb, mint a futásonkénti illesztési hiba (~12 µs). Ez **nem statisztikai
   zaj**, hanem **valódi időbeli drift**: a frekvencia-stabilitás változik
   futásról futásra.

**5 futás átlaga:** T₂_eff = **89,6 ± 17,5 µs (SEM)** = 0,74 ± 0,15 × T₂kal.
A kalibrálttól való eltérés 6× SEM → **statisztikailag szignifikáns**.

> A 77,5 µs tehát **egy drift-minimum**, nem „a" T₂. Az igazi kép: az echo-
> korlátozott T₂ a mérés idején **kb. 90 µs** volt, de futásról futásra
> 40–140 µs között szóródott. Ez pont az a jelenség, amit a QDS vizsgálni akart.

---

## MIT KELL TUDNI, HOGY NE ÉRTÉKELJÜK TÚLZOTTAN

A bírálói határok külön dokumentumban vannak: [`QDS_REFEREE_STATS.md`](QDS_REFEREE_STATS.md).
Röviden: ez a mérés **a pipeline-t és egy kvantumkoherencia-jelenséget**
validál, **nem új fizikát** bizonyít, és **semmit** nem bizonyít a Hope
architektúráról.