"""A kiértékelő logika tesztjei — szintetikus adatokon, hálózat nélkül.

Ezek a tesztek a mérés *értelmezését* védik: a τ-tengely ítélete a kontroll
karból jön, a T2-arány pedig a vizsgált effektus (nem időskála-hiba).
"""

import numpy as np
import pytest

from qds.constants import T1_CALIBRATED_US, T2_CALIBRATED_US, TAUS_US
from qds.model import (
    analytic,
    axis_verdict,
    fit_t1,
    fit_t2,
    ratio_difference,
    wilson_interval,
)


def _synthetic(t1_us=T1_CALIBRATED_US, t2_us=T2_CALIBRATED_US, noise_pct=0.0,
               seed=0):
    """A modellből generált, opcionálisan zajos echo/kontroll görbék."""
    echo, ctrl = analytic(TAUS_US, t1_us, t2_us)
    if noise_pct:
        rng = np.random.default_rng(seed)
        echo = echo + rng.normal(0, noise_pct, size=echo.shape)
        ctrl = ctrl + rng.normal(0, noise_pct, size=ctrl.shape)
    return echo, ctrl


def test_fit_recovers_t2_from_ideal_data():
    echo, _ = _synthetic()
    fit = fit_t2(TAUS_US, echo, T1_CALIBRATED_US)
    assert fit["t2_us"] == pytest.approx(T2_CALIBRATED_US, rel=0.02)
    assert fit["rms_pct"] < 0.5


def test_fit_recovers_t1_from_ideal_data():
    _, ctrl = _synthetic()
    fit = fit_t1(TAUS_US, ctrl)
    assert fit["t1_us"] == pytest.approx(T1_CALIBRATED_US, rel=0.02)
    assert abs(fit["offset_pct"]) < 0.3


def test_fit_returns_none_when_too_few_points():
    fit = fit_t2([0, 10], [100, 95], T1_CALIBRATED_US)
    assert fit["t2_us"] is None
    assert fit["n_points"] == 1
    assert fit_t1([0], [15])["t1_us"] is None


def test_shorter_t2_is_recovered():
    """Valódi extra dekoherencia (T2 < kalibrált) esetén is helyes a visszaadás."""
    echo, _ = _synthetic(t2_us=77.5)
    fit = fit_t2(TAUS_US, echo, T1_CALIBRATED_US)
    assert fit["t2_us"] == pytest.approx(77.5, rel=0.02)


def test_axis_verdict_uses_control_arm():
    ok = axis_verdict(1.12, 0.11)
    assert ok["axis_ok"] is True
    assert "RENDBEN" in ok["text"]

    bad = axis_verdict(0.64, 0.11)
    assert bad["axis_ok"] is False
    assert "ELTÉRÉS" in bad["text"]

    assert axis_verdict(None)["axis_ok"] is None


def test_ratio_difference_flags_same_timescale():
    """Ha mindkét kar ugyanazzal a faktorral tolódik, időskála-hiba a gyanú."""
    same = ratio_difference(0.80, 0.05, 0.80, 0.05)
    assert same["same_timescale"] is True
    assert same["n_sigma"] == pytest.approx(0.0, abs=1e-9)

    diff = ratio_difference(1.123, 0.109, 0.639, 0.106)
    assert diff["same_timescale"] is False
    assert abs(diff["difference"] - 0.484) < 1e-6
    assert diff["n_sigma"] > 3


def test_wilson_interval_properties():
    lo, hi = wilson_interval(99.51, 1024)
    assert lo < 99.51 < hi
    assert hi <= 100.0
    # 0%-nál a naiv intervallum 0 szélességű lenne, a Wilson nem
    lo0, hi0 = wilson_interval(0.0, 1024)
    assert lo0 == 0.0 and hi0 > 0.0
