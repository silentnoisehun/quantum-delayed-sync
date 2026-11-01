"""QDS — ábrák a MEGLÉVŐ adatokból (kvóta nélkül).

Négy panel (``results/figures/qds_overview.png``):

1. **Echo kar** a futások átlagával, a kalibrált-T2 modellgörbével és a
   futásonkénti pontokkal — ez a fő eredmény.
2. **Kontroll kar**: a T1-illesztés, ami a τ-tengely referenduma.
3. **Futásonkénti T2_eff**: a drift, ami a χ²-teszt tárgya (a hibasávok a
   görbe-illesztésből; a futás-átlagos driftről lásd a szöveges elemzést).
4. **Pearson-r ↔ kontraszt A** a wave-quantum kereszt-tesztből.

A számok a commitolt ``results/`` fájlokból jönnek, nem beégetve.

Használat::

    python qds_plots.py                 # mind a négy panel
    python qds_plots.py --no-wavezz     # csak a QDS panelek
"""

import argparse
import os
import sys

import matplotlib

matplotlib.use("Agg")  # fej nélküli futtatás (CI, szerver)
import matplotlib.pyplot as plt
import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.join(_HERE, "src")
if os.path.isdir(_SRC) and _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from qds.constants import TAUS_US  # noqa: E402
from qds.data import load_runs, multirun_summary, p0_series  # noqa: E402
from qds.model import analytic  # noqa: E402

RESULTS = os.path.join(_HERE, "results")
FIGDIR = os.path.join(RESULTS, "figures")

# színek: a két kar mindenhol ugyanazt kapja
C_ECHO = "#1f4e79"
C_CTRL = "#c55a11"
C_MODEL = "#7f7f7f"


def _style():
    plt.rcParams.update({
        "figure.dpi": 130,
        "savefig.dpi": 130,
        "font.size": 9,
        "axes.grid": True,
        "grid.alpha": 0.25,
        "axes.spines.top": False,
        "axes.spines.right": False,
    })


def panel_echo(ax, runs, summary):
    taus = np.asarray(TAUS_US, dtype=float)
    echo_mean = np.asarray(summary["echo_mean_pct"], dtype=float)
    echo_std = np.asarray(summary["echo_std_pct"], dtype=float)
    # futásonkénti pontok halványan
    for r in runs:
        ax.plot(taus, p0_series(r, "echo"), "o", ms=2.5, alpha=0.28,
                color=C_ECHO, zorder=2)
    ax.errorbar(taus, echo_mean, yerr=echo_std, fmt="o", ms=5, color=C_ECHO,
                capsize=2.5, lw=1.2, label="mért (5 futás átlaga ± szórás)",
                zorder=3)
    model, _ = analytic(taus, summary["t1_calibrated_us"],
                        summary["t2_calibrated_us"])
    ax.plot(taus, model, "--", color=C_MODEL, lw=1.4, label="modell (kalibrált T₂)",
            zorder=1)
    fit_t2 = summary["t2_eff_mean_us"]
    ax.set_title(f"Echo kar — T₂_eff = {fit_t2:.1f} µs "
                 f"({fit_t2 / summary['t2_calibrated_us']:.2f}× kalibrált)",
                 color=C_ECHO, fontsize=9.5, loc="left")
    ax.set_xlabel("τ (µs)")
    ax.set_ylabel("P(0) (%)")
    ax.set_xscale("symlog", linthresh=10)
    ax.set_xticks(taus)
    ax.set_xticklabels([str(int(t)) for t in taus])
    ax.legend(fontsize=7.5, loc="upper right")


def panel_ctrl(ax, runs, summary):
    taus = np.asarray(TAUS_US, dtype=float)
    ctrl_mean = np.asarray(summary["ctrl_mean_pct"], dtype=float)
    ctrl_std = np.asarray(summary["ctrl_std_pct"], dtype=float)
    for r in runs:
        ax.plot(taus, p0_series(r, "ctrl"), "o", ms=2.5, alpha=0.28,
                color=C_CTRL, zorder=2)
    ax.errorbar(taus, ctrl_mean, yerr=ctrl_std, fmt="o", ms=5, color=C_CTRL,
                capsize=2.5, lw=1.2, label="mért (5 futás átlaga ± szórás)",
                zorder=3)
    _, ctrl_model = analytic(taus, summary["t1_calibrated_us"],
                             summary["t2_calibrated_us"])
    ax.plot(taus, ctrl_model, "--", color=C_MODEL, lw=1.4,
            label="modell (kalibrált T₁)", zorder=1)
    t1_mean = summary["t1_eff_mean_us"]
    ax.set_title(f"Kontroll kar (csak T₁) — T₁_eff = {t1_mean:.1f} µs "
                 f"({t1_mean / summary['t1_calibrated_us']:.2f}× kalibrált)",
                 color=C_CTRL, fontsize=9.5, loc="left")
    ax.set_xlabel("τ (µs)")
    ax.set_ylabel("P(0) (%)")
    ax.set_xscale("symlog", linthresh=10)
    ax.set_xticks(taus)
    ax.set_xticklabels([str(int(t)) for t in taus])
    ax.legend(fontsize=7.5, loc="upper left")


def panel_drift(ax, summary):
    per = [r for r in summary["per_run"] if r["t2_eff_us"]]
    runs = [r["run"] for r in per]
    t2 = np.asarray([r["t2_eff_us"] for r in per])
    t2e = np.asarray([r["t2_stderr_us"] for r in per])
    t1 = np.asarray([r["t1_eff_us"] or np.nan for r in per])
    t1e = np.asarray([r["t1_stderr_us"] or np.nan for r in per])
    t2_cal = summary["t2_calibrated_us"]
    t1_cal = summary["t1_calibrated_us"]

    ax.axhline(t2_cal, color=C_ECHO, ls=":", lw=1.0, alpha=0.7)
    ax.errorbar(runs, t2, yerr=t2e, fmt="o", color=C_ECHO, ms=5, capsize=2.5,
                label="T₂_eff (echo kar)")
    ax.errorbar(np.asarray(runs) + 0.12, t1, yerr=t1e, fmt="s", color=C_CTRL,
                ms=4.5, capsize=2.5, label="T₁_eff (kontroll kar)")
    ax.axhline(t1_cal, color=C_CTRL, ls=":", lw=1.0, alpha=0.7)
    ax.set_title(f"Futásonkénti illesztés — T₂ szórás {np.std(t2, ddof=1):.1f} µs, "
                 f"T₁ szórás {np.nanstd(t1, ddof=1):.1f} µs",
                 fontsize=9.5, loc="left")
    ax.text(0.99, 0.02,
            f"szaggatott: kalibrált T₂ = {t2_cal:.1f} µs / T₁ = {t1_cal:.1f} µs",
            transform=ax.transAxes, ha="right", va="bottom", fontsize=6.8,
            color="#555555")
    ax.set_xlabel("futás")
    ax.set_ylabel("időállandó (µs)")
    ax.set_xticks(runs)
    ax.set_xticklabels([str(r) for r in runs])
    # a legendák/kapcsolók után is kényszerítsük az egész futásszámokat
    ax.xaxis.set_major_locator(matplotlib.ticker.FixedLocator(runs))
    ax.xaxis.set_major_formatter(matplotlib.ticker.FormatStrFormatter("%d"))
    ax.legend(fontsize=7.5, loc="center right")


def panel_wavezz(ax, results_dir=RESULTS):
    path = os.path.join(results_dir, "wave_zz_repeat_summary.json")
    if not os.path.exists(path):
        ax.set_visible(False)
        return False
    import json

    with open(path, encoding="utf-8") as f:
        s = json.load(f)
    r = s.get("pearson_r_per_run", [])
    a = s.get("contrast_a_per_run", [])
    runs = list(range(1, len(r) + 1))
    ax.plot(runs, r, "o-", color=C_ECHO, ms=5, lw=1.1)
    ax.set_ylim(min(r) - 0.0005, max(r) + 0.0005)
    ax.set_xlabel("futás")
    ax.set_ylabel("Pearson-r", color=C_ECHO)
    ax.tick_params(axis="y", labelcolor=C_ECHO)
    a_rel = s.get("contrast_a_relative_std_pct")
    a_stable = a_rel is not None and a_rel <= 10
    ax.set_title("wave-quantum kereszt-teszt: "
                 + (f"r és A is stabil (A szórás {a_rel:.1f}%)" if a_stable
                    else f"A ingadozik (A szórás {a_rel:.1f}%)"),
                 fontsize=9.5, loc="left")

    ax2 = ax.twinx()
    ax2.plot(runs, a, "s--", color=C_CTRL, ms=4.5, lw=1.1)
    ax2.set_ylabel("kontraszt A (max−min ⟨ZZ⟩)", color=C_CTRL)
    ax2.tick_params(axis="y", labelcolor=C_CTRL)
    ax2.grid(False)
    ax2.spines["right"].set_visible(True)
    ax.xaxis.set_major_locator(matplotlib.ticker.FixedLocator(runs))
    ax.xaxis.set_major_formatter(matplotlib.ticker.FormatStrFormatter("%d"))
    return True


def build(results_dir=RESULTS, figdir=FIGDIR, with_wavezz=True):
    """Elkészíti a PNG-t, visszaadja az útvonalát."""
    _style()
    runs = load_runs(results_dir)
    summary = multirun_summary(runs, TAUS_US)

    fig, axes = plt.subplots(2, 2, figsize=(10.6, 7.2))
    panel_echo(axes[0, 0], runs, summary)
    panel_ctrl(axes[0, 1], runs, summary)
    panel_drift(axes[1, 0], summary)
    if with_wavezz:
        panel_wavezz(axes[1, 1], results_dir)
    else:
        axes[1, 1].set_visible(False)

    fig.suptitle("Quantum Delayed Synchronization — U→delay(τ)→U† sweep, "
                 f"ibm_kingston qubit 91, {len(runs)} futás",
                 fontsize=11)
    fig.text(0.5, 0.008,
             "A hibasávok a futásonkénti görbe-illesztés hibái (nem a futások "
             "közti szórás). A pontok mögötti 1024 shot/pont statisztikai "
             "hibája a τ=800 esetén a legnagyobb.",
             ha="center", fontsize=6.8, color="#555555")
    fig.tight_layout(rect=(0, 0.02, 1, 0.96))
    os.makedirs(figdir, exist_ok=True)
    out = os.path.join(figdir, "qds_overview.png")
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description="QDS ábrák")
    parser.add_argument("--results-dir", default=RESULTS)
    parser.add_argument("--fig-dir", default=FIGDIR)
    parser.add_argument("--no-wavezz", action="store_true")
    args = parser.parse_args(argv)
    out = build(args.results_dir, args.fig_dir, not args.no_wavezz)
    print(f"mentve: {os.path.relpath(out, _HERE)}")
    return 0


if __name__ == "__main__":
    from qds.cli import run

    sys.exit(run(main))
