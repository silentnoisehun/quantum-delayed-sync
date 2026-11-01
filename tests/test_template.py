"""A publikált áramkör-hash és a τ→dt konverzió ellenőrzése.

Ez a legfontosabb regressziós teszt: a ``results/circuit_hashes.json``-ban
publikált SHA-256 azt bizonyítja, hogy minden futás ugyanazt a fizikai láncot
építette. Ha a sablon (szögek, τ-rács, kapuk sorrendje) vagy a hash számítása
megváltozik, a hash is megváltozik — a teszt ezt azonnal kiszúrja.
"""

import json
import os

import pytest

from qds.circuits import build_circuits, circuit_hash, tau_to_dt, template_hash
from qds.constants import DT_SEC, TAUS_US

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HASH_FILE = os.path.join(HERE, "results", "circuit_hashes.json")


def _published_hash():
    if not os.path.exists(HASH_FILE):
        pytest.skip("results/circuit_hashes.json hiányzik")
    with open(HASH_FILE, encoding="utf-8") as f:
        return json.load(f)["template_sha256"]


def test_template_hash_is_reproducible():
    """A kódból számolt hash == a publikált hash (a mérések integritása)."""
    assert template_hash() == _published_hash()


def test_template_hash_is_stable_across_calls():
    assert template_hash() == template_hash()


def test_build_circuits_shape():
    circuits = build_circuits(unit="us")
    assert len(circuits) == len(TAUS_US)
    for tau, dur, qc_e, qc_c in circuits:
        assert dur == tau
        for qc in (qc_e, qc_c):
            assert qc.num_qubits == 1
            assert "measure" in qc.count_ops()


def test_echo_has_inverse_control_does_not():
    """Az echo karban ott van az U† (2 db U kapu), a kontrollban nincs."""
    by_tau = {tau: (e, c) for tau, _d, e, c in build_circuits(unit="us")}
    echo, ctrl = by_tau[50]
    assert echo.count_ops().get("u", 0) == 2
    assert ctrl.count_ops().get("u", 0) == 1
    assert "delay" in echo.count_ops()
    assert "delay" in ctrl.count_ops()


def test_delay_durations_are_physical_microseconds():
    """A hardveres áramkör a τ-t FIZIKAI időben adja meg, nem dt-ben."""
    for tau, _dur, qc_e, _qc_c in build_circuits(unit="us"):
        delays = [inst.operation for inst in qc_e.data
                  if inst.operation.name == "delay"]
        if tau == 0:
            assert not delays
        else:
            assert delays[0].unit == "us"
            assert delays[0].duration == tau


def test_tau_to_dt_aligns_to_granularity():
    assert tau_to_dt(10, DT_SEC) == 44992
    for tau in TAUS_US[1:]:
        assert tau_to_dt(tau, DT_SEC) % 16 == 0


def test_tau_to_dt_rejects_zero_dt():
    with pytest.raises(ZeroDivisionError):
        tau_to_dt(10, 0)


def test_invalid_unit_raises():
    with pytest.raises(ValueError):
        build_circuits(unit="ns")
    with pytest.raises(ValueError):
        build_circuits(unit="dt", dt=None)


def test_hash_changes_when_template_changes():
    """Ha a τ-rács vagy a szög változik, a hash-nek változnia kell."""
    base = circuit_hash(build_circuits(unit="us"))
    assert circuit_hash(build_circuits(unit="us", theta=1.0)) != base
    assert circuit_hash(build_circuits(unit="us", taus_us=(0, 10))) != base
