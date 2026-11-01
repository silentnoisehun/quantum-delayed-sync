"""Az analitikus modellek és a τ=0 referencia ellenőrzése.

Korábbi verzió: a teszt saját, lokális ``theta``-t húzott
(``np.random.seed(42)``), és a *szimulátor* median T1/T2-jével (242/143 µs)
számolt. Így a teszt akkor is zöld maradt volna, ha a valódi mérés
konstansai elromlanak. Most a közös :mod:`qds.model` / :mod:`qds.constants`
modult teszteli, a kalibrált 91-es qubit értékeivel.
"""

import numpy as np

from qds.constants import CTRL_P0_AT_ZERO_PCT, T1_CALIBRATED_US, T2_CALIBRATED_US, THETA
from qds.model import analytic, ctrl_model, echo_model


def test_theta_matches_known_value():
    assert abs(THETA - 2.3533) < 0.01, f"theta={THETA}, expected ~2.3533"


def test_ctrl_tau0_is_1475_percent():
    assert abs(CTRL_P0_AT_ZERO_PCT - 14.75) < 0.05


def test_echo_decays_with_tau():
    taus = [0, 10, 25, 50, 100, 200, 400, 800]
    echo, _ctrl = analytic(taus, T1_CALIBRATED_US, T2_CALIBRATED_US)
    assert np.all(np.diff(echo) < 0), f"az echo nem monoton csökken: {echo}"
    assert abs(echo[0] - 100.0) < 1.0, f"tau=0 echo={echo[0]}%, ~100% kellene"
    assert echo[-1] < 30, f"tau=800 echo={echo[-1]}%, 30% alatt kellene"


def test_ctrl_recovers_to_high_p0():
    _echo, ctrl = analytic([0, 800], T1_CALIBRATED_US, T2_CALIBRATED_US)
    assert abs(ctrl[0] - 14.75) < 0.1, f"tau=0 ctrl={ctrl[0]}%, ~14.75% kellene"
    assert ctrl[1] > 90, f"tau=800 ctrl={ctrl[1]}%, a T1-relaxáció ~96%"


def test_analytic_scalar_input():
    """A `qds_analyze` skalár τ-t ad át — ennek is működnie kell."""
    pe, pc = analytic(50, T1_CALIBRATED_US, T2_CALIBRATED_US)
    assert 75.0 < float(pe) < 85.0
    assert 28.0 < float(pc) < 32.0


def test_models_agree_with_analytic():
    """A fit-modellek (másodpercben) és az analitikus modell ugyanaz."""
    taus_us = np.array([0, 10, 100, 800], dtype=float)
    pe, pc = analytic(taus_us, T1_CALIBRATED_US, T2_CALIBRATED_US)
    for i, tau in enumerate(taus_us):
        t = tau * 1e-6
        assert abs(echo_model(np.array([t]), T2_CALIBRATED_US * 1e-6)[0] * 100
                   - pe[i]) < 1e-9
        assert abs(ctrl_model(np.array([t]), T1_CALIBRATED_US * 1e-6)[0] * 100
                   - pc[i]) < 1e-9
