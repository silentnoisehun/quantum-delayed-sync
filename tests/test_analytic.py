# tests/test_analytic.py
import numpy as np

np.random.seed(42)
theta = float(np.random.uniform(0, 2*np.pi))

# theta=2.3533 -> cos^2(theta/2) = 0.1475 (14.75%)
def test_theta_matches_known_value():
    assert abs(theta - 2.3533) < 0.01, f"theta={theta}, expected ~2.3533"

def test_ctrl_tau0_is_1475_percent():
    expected = np.cos(theta/2)**2 * 100
    assert abs(expected - 14.75) < 0.05

def test_echo_decays_with_tau():
    T1 = 242e-6
    T2 = 143e-6
    c = np.cos(theta)
    s2 = np.sin(theta)**2

    def p_echo(tau):
        e1 = np.exp(-tau / T1)
        e2 = np.exp(-tau / T2)
        return 0.5 + 0.5 * (e2 * s2 + e1 * c * c + c * (1 - e1))

    p0 = p_echo(0) * 100
    p_800us = p_echo(800e-6) * 100
    assert p0 > p_800us, "Echo should decay with tau"
    assert abs(p0 - 100.0) < 1.0, f"tau=0 echo={p0}%, expected ~100%"

def test_ctrl_r1_is_low():
    T1 = 242e-6
    def p_ctrl(tau):
        e1 = np.exp(-tau / T1)
        return 0.5 + 0.5 * (1 + (np.cos(theta) - 1) * e1)
    # a fuggveny VALOSZINUSEGET ad (0..1), az assertion szazalekot vart ->
    # ez a ketto kulonbso egységben hasonlito, ezert a *100 a helyes
    p0 = p_ctrl(0) * 100
    assert abs(p0 - 14.75) < 0.1, f"tau=0 ctrl={p0}%, expected ~14.75%"
    assert p_ctrl(800e-6) * 100 > 90.0, "Control should recover to ~96% (T1 relaxation)"
