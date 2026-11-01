"""Az adatbeolvasás és a több futás statisztikájának tesztjei a repó valódi
adataival — hálózat és token nélkül.

Ezek a tesztek azt hivatottak megakadályozni, hogy a publikált számok
(``T2_eff = 89,6 ± 39,2 µs``, ``T1/T1kal = 1,08``) észrevétlenül elmozduljanak.
"""

import json
import os

import numpy as np
import pytest

from qds.constants import TAUS_US
from qds.data import heterogeneity_chi2, load_runs, multirun_summary, p0_series

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(HERE, "results")


@pytest.fixture(scope="module")
def runs():
    if not os.path.exists(os.path.join(RESULTS, "raw_counts_all_runs.json")):
        pytest.skip("nincs nyers futásadat")
    return load_runs(RESULTS)


@pytest.fixture(scope="module")
def summary(runs):
    return multirun_summary(runs, TAUS_US)


def test_load_runs_order_and_shape(runs):
    assert [r["run"] for r in runs] == [1, 2, 3, 4, 5]
    for r in runs:
        assert len(r["points"]) == 2 * len(TAUS_US)


def test_all_counts_are_1024_shots(runs):
    for r in runs:
        for p in r["points"]:
            assert sum(p["counts"].values()) == 1024
            assert 0 <= p["p0_pct"] <= 100


def test_p0_series_matches_raw_counts(runs):
    echo = p0_series(runs[0], "echo")
    assert echo.shape == (len(TAUS_US),)
    assert echo[0] == pytest.approx(99.51171875)
    assert np.all(np.diff(echo) < 0), "az echo görbe nem monoton csökken"


def test_p0_series_missing_point_is_nan(runs):
    broken = {"points": [p for p in runs[0]["points"] if p["tau_us"] != 50]}
    series = p0_series(broken, "echo")
    assert np.isnan(series[list(TAUS_US).index(50)])
    assert np.isfinite(series).sum() == len(TAUS_US) - 1


def test_summary_reproduces_published_numbers(summary):
    """A publikált értékek: T2_eff 89,6 ± 39,2 µs, T1_eff 273,8 µs, 5/5 monoton."""
    assert summary["n_runs"] == 5
    assert summary["t2_eff_mean_us"] == pytest.approx(89.63, abs=0.05)
    assert summary["t2_eff_std_us"] == pytest.approx(39.18, abs=0.05)
    assert summary["t2_eff_sem_us"] == pytest.approx(17.52, abs=0.05)
    assert summary["t1_eff_mean_us"] == pytest.approx(273.86, abs=0.05)
    assert summary["t1_eff_std_us"] == pytest.approx(37.21, abs=0.05)
    assert summary["monotonia_runs_ok"] == {"echo": 5, "ctrl": 5}


def test_per_run_fits_match_published_table(summary):
    expected = [(77.5, 285.5), (43.1, 211.6), (140.8, 272.6),
                (117.7, 309.3), (69.1, 290.3)]
    for rec, (t2, t1) in zip(summary["per_run"], expected, strict=True):
        assert rec["t2_eff_us"] == pytest.approx(t2, abs=0.1)
        assert rec["t1_eff_us"] == pytest.approx(t1, abs=0.1)


def test_heterogeneity_chi2_matches_published_result(summary):
    per = summary["per_run"]
    t2 = [r["t2_eff_us"] for r in per]
    se = [r["t2_stderr_us"] for r in per]
    d = heterogeneity_chi2(t2, se)
    assert d["dof"] == 4
    assert d["chi2"] == pytest.approx(60.9, abs=0.5)
    assert d["p_value"] < 1e-9
    assert "NEM fér bele" in d["verdict"]

    t1 = [r["t1_eff_us"] for r in per]
    se1 = [r["t1_stderr_us"] for r in per]
    d1 = heterogeneity_chi2(t1, se1)
    assert d1["p_value"] > 0.01, "a T1 nem mutathat szignifikáns ingadozást"


def test_chi2_rejects_bad_input():
    with pytest.raises(ValueError):
        heterogeneity_chi2([1.0], [0.1])
    with pytest.raises(ValueError):
        heterogeneity_chi2([1.0, 2.0], [0.1])


def test_committed_multirun_stats_is_in_sync(summary):
    """A repóban commitolt multirun_stats.json ne csússzon el a számítástól."""
    path = os.path.join(RESULTS, "multirun_stats.json")
    with open(path, encoding="utf-8") as f:
        on_disk = json.load(f)
    assert on_disk["n_runs"] == summary["n_runs"]
    for key in ("echo_mean_pct", "ctrl_mean_pct",
                "t2_eff_mean_us", "t1_eff_mean_us"):
        # 1e-6 relatív: a fit utolsó jegyei platformonként eltérhetnek, a
        # publikált érték viszont nem mozdulhat.
        assert on_disk[key] == pytest.approx(summary[key], rel=1e-6), key
