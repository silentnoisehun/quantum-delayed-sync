"""A kvóta nélküli eszközök tesztjei: robusztusság, ábra, offline elemzés.

Ezek a tesztek azt védik, hogy a „kvóta nélkül is újrafuttatható” ígéret
valóban teljesüljön: ne kelljen token, ne induljon hálózati hívás, és a
meglévő adatokból ugyanazok a számok jöjjenek ki.
"""

import json
import os
import sys

import numpy as np
import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(HERE, "results")

sys.path.insert(0, HERE)

import qds_robustness as R  # noqa: E402
import qds_wavezz_repeat as W  # noqa: E402
from qds.constants import TAUS_US  # noqa: E402
from qds.data import load_runs, multirun_summary  # noqa: E402
from qds.model import fit_t2  # noqa: E402


@pytest.fixture(scope="module")
def runs():
    return load_runs(RESULTS)


@pytest.fixture(scope="module")
def summary(runs):
    return multirun_summary(runs, TAUS_US)


def test_shot_sigma_is_binomial():
    sigma = R.shot_sigma_pct([50.0, 100.0, 0.0], shots=1024)
    assert sigma[0] == pytest.approx(np.sqrt(0.25 / 1024) * 100, rel=1e-6)
    # 100 % / 0 % közelében a variancia a 1e-6-os padló miatt ~0 (nem 0,031)
    assert sigma[1] < 0.01
    assert sigma[2] < 0.01
    assert sigma[1] < sigma[0] and sigma[2] < sigma[0]


def test_bootstrap_contains_point_estimate(runs, summary):
    res = R.analyse_series(np.asarray(TAUS_US, float),
                           np.asarray(summary["echo_mean_pct"], float),
                           np.asarray(summary["ctrl_mean_pct"], float),
                           summary["t1_calibrated_us"], bootstrap_n=200)
    b = res["t2_bootstrap"]
    assert b["n_ok"] == 200
    assert b["ci_low"] < res["t2_point_us"] < b["ci_high"]
    # a T1 bootstrap ugyanarra a nagyságrendre essen, mint a pontbecslés
    b1 = res["t1_bootstrap"]
    assert b1["ci_low"] < res["t1_point_us"] < b1["ci_high"], (
        "a T1-bootstrap nem a T1 körül van — valószínűleg rossz paramétert kap")


def test_bootstrap_is_reproducible(runs):
    taus = np.asarray(TAUS_US, float)
    y = np.asarray([p["p0_pct"] for p in runs[0]["points"]
                    if p["arm"] == "echo"], float)
    a = R.bootstrap_fit(taus, y, lambda t, v: fit_t2(t, v, 254.16), "t2_us", n=50)
    b = R.bootstrap_fit(taus, y, lambda t, v: fit_t2(t, v, 254.16), "t2_us", n=50)
    assert a["std"] == b["std"]


def test_weighted_and_truncation_agree_with_full_fit(summary):
    res = R.analyse_series(np.asarray(TAUS_US, float),
                           np.asarray(summary["echo_mean_pct"], float),
                           np.asarray(summary["ctrl_mean_pct"], float),
                           summary["t1_calibrated_us"], bootstrap_n=20)
    assert abs(res["t2_weighted"]["rel_diff_pct"]) < 10, "a súlyozás nem boríthatja fel az eredményt"
    tr = res["t2_truncation"]
    for key in ("full", "up_to_400us", "up_to_200us"):
        assert tr[key] is not None
        # a hosszú τ-k elhagyása nem változtathatja meg drasztikusan a T2-t
        assert abs(tr[key]["t2_us"] - tr["full"]["t2_us"]) < 0.3 * tr["full"]["t2_us"], key


def test_offline_wavezz_analysis_needs_no_network(capsys):
    runs = W.load_saved_runs(RESULTS)
    assert len(runs) == 5
    checks = W._self_checks(runs)
    assert checks["mismatches"] == 0, "a mentett r/A nem egyezik a rows-ból újraszámolttal"
    summary = W.summarize(runs)
    assert summary["r_mean"] == pytest.approx(0.9994, abs=5e-4)
    assert summary["contrast_a_mean"] == pytest.approx(1.5076, abs=5e-3)
    assert summary["contrast_a_relative_std_pct"] < 10
    assert "STABIL" in summary["verdict"]


def test_offline_summary_keeps_metadata(tmp_path):
    runs = W.load_saved_runs(RESULTS)
    W.save_summary(runs, results_dir=str(tmp_path))
    with open(tmp_path / "wave_zz_repeat_summary.json", encoding="utf-8") as f:
        saved = json.load(f)
    assert saved["backend"] == "ibm_kingston"
    assert saved["shots"] == 2048
    assert len(saved["layout"]) == 14
    assert saved["qds_t2eff_mean_us"] is not None
    assert len(saved["runs"]) == 5


def test_plots_build_offline(tmp_path):
    """Az ábra elkészül token nélkül, és valódi PNG-t ad."""
    pytest.importorskip("matplotlib")
    import qds_plots as P

    out = P.build(RESULTS, str(tmp_path), with_wavezz=True)
    assert os.path.exists(out)
    assert os.path.getsize(out) > 20_000
    with open(out, "rb") as f:
        assert f.read(8) == b"\x89PNG\r\n\x1a\n"
