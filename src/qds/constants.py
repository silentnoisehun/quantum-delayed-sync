"""A QDS mérés közös konstansai — egyetlen igazságforrás.

Korábban a `BACKEND_NAME`, `QUBIT`, `TAUS_US` és a `THETA` érték **nyolc**
fájlban volt külön-külön beégetve (hahn_echo_t2_qam.py, qds_analyze.py,
qds_axis_arbitration.py, qds_multirun_stats.py, qds_replicates.py,
qds_recover_job.py, qds_wavezz_repeat.py, qds_target_probe.py). Egyetlen
elgépelés bármelyikben csendben más mérést eredményezett volna, ezért most
innen jönnek.
"""

import math

# --- Cél hardver ---------------------------------------------------------
BACKEND_NAME = "ibm_kingston"
QUBIT = 91
SHOTS = 1024

# --- A τ-sweep rácsa (µs) ------------------------------------------------
TAUS_US = (0, 10, 25, 50, 100, 200, 400, 800)

# --- A mérés pillanatában kiolvasott kalibráció (qubit 91, 2026-10-18) ---
# FIGYELEM: ezek NEM konstans fizikai értékek, hanem egy adott időpontban
# lekérdezett kalibráció. A futásonkénti JSON-okban is ott van a saját
# `t1_calibrated_us` / `t2_calibrated_us` érték; ez csak visszaeső (fallback)
# alapérték, ha egy régi adatfájlból hiányzik.
T1_CALIBRATED_US = 254.1627621299776
T2_CALIBRATED_US = 121.25600306875532

# --- A random-axis U kapu szögei ----------------------------------------
# Ezek az értékek a `np.random.seed(42)` utáni első három `uniform(0, 2π)`
# húzásból származnak (2026-10-18). Szándékosan **explicit** konstansként
# szerepelnek, nem futásidőben generálódnak: így a publikált
# `template_sha256` nem függ a telepített numpy RNG-implementációjától.
THETA = 2.353304971691044
PHI = 5.9735141613602165
LAMBDA = 4.599253580133889

# --- Kontroll-referencia -------------------------------------------------
# τ=0-nál a kontroll kar elvárt P(0)-ja: cos²(theta/2) ≈ 14,75 %.
CTRL_P0_AT_ZERO_PCT = math.cos(THETA / 2) ** 2 * 100

# --- Szimulátor (MEDIAN zajmodell — NEM a 91-es qubit értékei!) ---------
SIM_T1_US = 242.0
SIM_T2_US = 143.0
SIM_READOUT = 0.0098
SIM_1Q_ERR = 3.5e-4
# A szimulátor áramköre dt-egységben épül; 4,5 GHz-es mintavételt feltételez.
DT_SEC = 1 / 4.5e9
DT_GRANULARITY = 16
