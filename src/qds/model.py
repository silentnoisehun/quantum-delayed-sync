"""Analitikus modellek és illesztések a QDS méréshez.

A modellek a ``U → delay(τ) → U†`` (echo) és ``U → delay(τ)`` (kontroll) kar
P(0) valószínűségét adják meg, a qubit kalibrált T1/T2-jével.

A kontroll kar **csak T1-től függ** — ezért ő az időskála referenduma: ha egy
rejtett időskálázó hiba van, mindkét kar görbéjét ugyanazzal az aránnyal
tolja el, míg valódi extra dekoherencia csak az echo kart rontja el.

A formális levezetés (a dokumentációban is ez szerepel):

  P_echo(τ) = ½ + ½·[e^{-τ/T2}·sin²θ + e^{-τ/T1}·cos²θ + cosθ·(1 - e^{-τ/T1})]
  P_ctrl(τ) = ½ + ½·[1 + (cosθ - 1)·e^{-τ/T1}]
"""

import numpy as np

from qds.constants import T1_CALIBRATED_US, T2_CALIBRATED_US, THETA


def analytic(taus_us, t1_us=T1_CALIBRATED_US, t2_us=T2_CALIBRATED_US,
             theta=THETA):
    """Visszaadja (echo_pct, ctrl_pct) tömböket a megadott τ-kra.

    Args:
        taus_us: τ érték(ek) mikroszekundumban (skalár vagy tömb).
        t1_us: T1 mikroszekundumban.
        t2_us: T2 mikroszekundumban.
        theta: a random-axis U kapu szöge (radián).
    """
    taus = np.asarray(taus_us, dtype=float)
    c, s2 = np.cos(theta), np.sin(theta) ** 2
    e1 = np.exp(-taus / t1_us) if t1_us else np.ones_like(taus)
    e2 = np.exp(-taus / t2_us) if t2_us else np.zeros_like(taus)
    p_echo = 0.5 + 0.5 * (e2 * s2 + e1 * c * c + c * (1 - e1))
    p_ctrl = 0.5 + 0.5 * (1 + (c - 1) * e1)
    return p_echo * 100, p_ctrl * 100


def echo_model(t, t2, t1=T1_CALIBRATED_US * 1e-6, theta=THETA):
    """Echo kar modell (másodpercben), T1 rögzítve, T2 a szabad paraméter."""
    c, s2 = np.cos(theta), np.sin(theta) ** 2
    e1 = np.exp(-t / t1)
    return 0.5 + 0.5 * (np.exp(-t / t2) * s2 + e1 * c * c + c * (1 - e1))


def ctrl_model(t, t1, p0_off=0.0, theta=THETA):
    """Kontroll kar modell (másodpercben): csak T1 és egy konstans offset."""
    c = np.cos(theta)
    return 0.5 + 0.5 * (1 + (c - 1) * np.exp(-t / t1)) + p0_off


def fit_t2(taus_us, echo_pct, t1_us=T1_CALIBRATED_US, theta=THETA):
    """Az echo görbére illesztett T2_eff.

    Args:
        taus_us: τ értékek mikroszekundumban.
        echo_pct: P(0) százalékban, azonos sorrendben.
        t1_us: a kalibrált T1 (rögzítve).
        theta: a kapu szöge.

    Returns:
        dict: ``t2_us``, ``stderr_us``, ``rms_pct``, ``curve_pct`` (illesztett
        görbe MINDEN τ-ra) és ``n_points``. Ha nem illeszthető (kevesebb mint
        3 pozitív τ, vagy scipy hiba), minden érték ``None``, kivéve
        ``n_points``.
    """
    from scipy.optimize import curve_fit

    taus = np.asarray(taus_us, dtype=float)
    y = np.asarray(echo_pct, dtype=float) / 100.0
    t = taus * 1e-6
    mask = taus > 0
    empty = {"t2_us": None, "stderr_us": None, "rms_pct": None,
             "curve_pct": None, "n_points": int(mask.sum())}
    if mask.sum() < 3:
        return empty
    t1_s = t1_us * 1e-6
    try:
        popt, pcov = curve_fit(
            lambda tt, t2: echo_model(tt, t2, t1_s, theta),
            t[mask], y[mask], p0=[150e-6], bounds=([1e-8], [20e-3]),
        )
    except Exception:
        return empty
    t2 = float(popt[0])
    stderr = float(np.sqrt(pcov[0][0])) if np.isfinite(pcov[0][0]) else float("nan")
    pred = echo_model(t[mask], t2, t1_s, theta) * 100
    rms = float(np.sqrt(np.mean((y[mask] * 100 - pred) ** 2)))
    return {
        "t2_us": t2 * 1e6,
        "stderr_us": stderr * 1e6,
        "rms_pct": rms,
        "curve_pct": echo_model(t, t2, t1_s, theta) * 100,
        "n_points": int(mask.sum()),
    }


def fit_t1(taus_us, ctrl_pct, theta=THETA):
    """A kontroll görbére illesztett T1_eff (+ konstans offset).

    Returns:
        dict: ``t1_us``, ``stderr_us``, ``offset_pct``, ``rms_pct``,
        ``curve_pct``. Nem illeszthető esetben ``None`` értékek.
    """
    from scipy.optimize import curve_fit

    taus = np.asarray(taus_us, dtype=float)
    y = np.asarray(ctrl_pct, dtype=float) / 100.0
    t = taus * 1e-6
    mask = taus > 0
    empty = {"t1_us": None, "stderr_us": None, "offset_pct": None,
             "rms_pct": None, "curve_pct": None}
    if mask.sum() < 3:
        return empty
    try:
        popt, pcov = curve_fit(
            lambda tt, t1, off: ctrl_model(tt, t1, off, theta),
            t[mask], y[mask], p0=[250e-6, 0.0],
            bounds=([50e-6, -0.02], [1e-3, 0.02]),
        )
    except Exception:
        return empty
    t1 = float(popt[0])
    stderr = float(np.sqrt(pcov[0][0])) if np.isfinite(pcov[0][0]) else float("nan")
    pred = ctrl_model(t[mask], t1, float(popt[1]), theta) * 100
    rms = float(np.sqrt(np.mean((y[mask] * 100 - pred) ** 2)))
    return {
        "t1_us": t1 * 1e6,
        "stderr_us": stderr * 1e6,
        "offset_pct": float(popt[1]) * 100,
        "rms_pct": rms,
        "curve_pct": ctrl_model(t, t1, float(popt[1]), theta) * 100,
    }


def axis_verdict(t1_ratio, t1_ratio_err=None, tol=0.15):
    """A τ-tengely ítélete — KIZÁRÓLAG a kontroll karból.

    Miért nem a T2-arányból? Mert a T2_eff/T2_kalibrált arány pontosan az a
    mennyiség, amit a mérés *vizsgálni* akar (echo-korlátozott dekoherencia).
    Ha abból ítélnénk, a keresett effektust neveznénk ki időskála-hibának —
    ezt tette a korábbi ``qds_analyze.py`` („ELTÖRÉS”), miközben a
    ``QDS_CHRONICLE.md`` helyesen a kontroll karból „RENDBEN”-t kapott.
    A két szkript most ugyanazt az ítéletet adja.

    Args:
        t1_ratio: T1_eff / T1_kalibrált arány (a kontroll karból) vagy ``None``.
        t1_ratio_err: az arány standard hibája (opcionális).
        tol: az elfogadási sáv félszélessége, ha nincs hibabecslés.

    Returns:
        dict: ``axis_ok`` (bool vagy None), ``text`` (kiírható mondat).
    """
    if not t1_ratio:
        return {"axis_ok": None,
                "text": "nem eldönthető — nincs kalibrált T1 a kontroll karhoz"}
    lo, hi = 1.0 - tol, 1.0 + tol
    band = f"{lo:.2f}–{hi:.2f}"
    if 0.85 < t1_ratio < 1.25:
        txt = (f"RENDBEN — a kontroll kar T1-aránya {t1_ratio:.3f}"
               + (f" ± {t1_ratio_err:.3f}" if t1_ratio_err else "")
               + ", konzisztens 1,0-val; a τ-tengely helyes, a T2-deficit "
                 "valódi dekoherencia")
        return {"axis_ok": True, "text": txt}
    txt = (f"ELTÉRÉS — a kontroll kar T1-aránya {t1_ratio:.3f}"
           + (f" ± {t1_ratio_err:.3f}" if t1_ratio_err else "")
           + f", kívül a {band} sávon; rejtett időskálázó hiba gyanúja")
    return {"axis_ok": False, "text": txt}


def ratio_difference(r1, r1_err, r2, r2_err):
    """Két arány (T1 vs T2) különbségének szignifikanciája.

    Ha rejtett időskálázó hiba van, mindkét arány **ugyanazzal** a faktorral
    térne el 1,0-tól. Ha a T1 arány ≈ 1 és a T2 arány ≪ 1, akkor valódi
    extra dekoherencia van az echo karban.

    Returns:
        dict: ``difference``, ``sigma`` (kombinált hiba), ``n_sigma``,
        ``same_timescale`` (bool: a különbség < 2σ).
    """
    diff = r1 - r2
    sigma = (r1_err ** 2 + r2_err ** 2) ** 0.5
    n_sigma = abs(diff) / sigma if sigma else float("inf")
    return {"difference": diff, "sigma": sigma, "n_sigma": n_sigma,
            "same_timescale": n_sigma < 2.0}


def wilson_interval(p0_pct, shots=1024, z=1.959963984540054):
    """A mért P(0) Wilson-féle 95 %-os konfidenciaintervalluma (százalékban).

    A 1024 shotos binomiális mérésnél a naiv ±1,96·√(p(1-p)/n) hiba a
    széleken (p ≈ 0 vagy 1 közelében) alulbecsül; a Wilson-intervallum
    mindenhol helyes lefedettséget ad. Erre a fitelt T2 hibasávjának
    értelmezéséhez van szükség.
    """
    p = float(p0_pct) / 100.0
    n = float(shots)
    denom = 1.0 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return max(0.0, (centre - half) * 100), min(100.0, (centre + half) * 100)
