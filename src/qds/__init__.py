"""QDS — Quantum Delayed Synchronization közös mag.

Ez a csomag tartalmazza a repository összes végrehajtható szkriptje által
használt közös definíciókat (konstansok, áramkör-építés, illesztő modellek,
adatbeolvasás, IBM kapcsolat). A gyökérben lévő `qds_*.py` és
`hahn_echo_t2_qam.py` szkriptek ezekre épülnek, hogy a konstansok és a
fizikai modellek **egy helyen** legyenek definiálva.

Fontos: a `theta`/`phi`/`lam` szögek és a τ-rács rögzítettek, mert a
`results/circuit_hashes.json`-ban publikált SHA-256 hash ezekből számolódik.
Ha bármelyik változik, a hash is változik, és a korábbi futásokkal való
összehasonlíthatóság megszűnik.
"""

from qds.constants import (
    BACKEND_NAME,
    LAMBDA,
    PHI,
    QUBIT,
    SHOTS,
    T1_CALIBRATED_US,
    T2_CALIBRATED_US,
    TAUS_US,
    THETA,
)

__all__ = [
    "BACKEND_NAME",
    "LAMBDA",
    "PHI",
    "QUBIT",
    "SHOTS",
    "T1_CALIBRATED_US",
    "T2_CALIBRATED_US",
    "TAUS_US",
    "THETA",
]

__version__ = "0.2.0"
