"""QDS — dt-igazolás a MÁR MEGFIGYELT jobokból (KVÓTA NÉLKÜL).

Kérdés: a platform ``dt = 4 ns``-ot ír (250 MHz), ami pulzálási
mintavételi rátaként irreális egy ~5 GHz-es qubitnél. A valódi, fizikai
időzítést az ISA-metaadatok és a mért késleltetések hossza árulja el.

A szkript **nem indít új jobot** → nem fogyaszt kvótát. Két forrásból dolgozik:

1. `backend.target` (élő, ha van token): ``dt``, ``granularity``,
   ``pulse_alignment`` és a kapuk dt-hossza;
2. a repóban lévő ``results/qam_echo_*.json`` fájlok ``isa`` mezője
   (offline is működik).

Fontos: a ``delay`` τ-t **fizikai időben (µs)** adjuk meg, és a transzpiler
konvertálja a cél dt-jével, ezért a τ-tengely konverziója konzisztens
(ellenőrzés: ``qds_env_check.py``). A dt nominális volta miatt a τ-tengely
**empirikus** referenduma továbbra is a kontroll kar (csak T1-től függ).

Használat::

    python qds_dt_probe.py [--offline]
"""

import argparse
import glob
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.join(_HERE, "src")
if os.path.isdir(_SRC) and _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from qds.constants import BACKEND_NAME  # noqa: E402

# A Heron r2 valószínű tényleges mintavételi lépése (összehasonlítási alap).
CANDIDATE_DTS = (2.222e-10, 4e-9)


def _print_target(backend, name):
    tgt = backend.target
    print(f"Backend: {name}")
    print(f"  target.dt            = {tgt.dt}")
    print(f"  target.granularity   = {tgt.granularity}")
    print(f"  target.pulse_alignment = {tgt.pulse_alignment}")
    if tgt.dt:
        for gate in ("sx", "x", "rz"):
            try:
                inst = tgt.operation_from_name(gate)
                dur = getattr(inst, "duration", None)
                if dur:
                    print(f"  {gate:<3} duration = {dur} dt "
                          f"({dur * tgt.dt * 1e9:.2f} ns a target dt-jével, "
                          f"{dur * CANDIDATE_DTS[0] * 1e9:.2f} ns "
                          f"dt=0.222 ns mellett)")
            except Exception:
                continue


def _scan_local_results(results_dir):
    """A repóban lévő eredményfájlok ISA-metaadatai (token nélkül is)."""
    print("-" * 72)
    files = sorted(glob.glob(os.path.join(results_dir, "qam_echo_*.json")))
    if not files:
        print("Nincs helyi eredményfájl (results/qam_echo_*.json).")
        return
    for fn in files:
        with open(fn, encoding="utf-8") as f:
            data = json.load(f)
        isa = data.get("isa") or {}
        print(f"{os.path.basename(fn)}: isa.dt={isa.get('dt')} "
              f"granularity={isa.get('granularity')}")
    dry = os.path.join(results_dir, "qam_echo_t2_dryrun.json")
    if os.path.exists(dry):
        with open(dry, encoding="utf-8") as f:
            diag = json.load(f).get("diagnostics", {})
        print(f"qam_echo_t2_dryrun.json: target_dt={diag.get('target_dt')} "
              f"({(diag.get('target_dt') or 0) * 1e9:.3f} ns)")


def main(argv=None):
    parser = argparse.ArgumentParser(description="QDS dt-vizsgálat")
    parser.add_argument("--offline", action="store_true",
                        help="token nélkül: csak a helyi eredmények ISA-mezői")
    parser.add_argument("--backend", default=BACKEND_NAME)
    args = parser.parse_args(argv)

    if not args.offline:
        try:
            from qds.ibm import get_backend
            _print_target(get_backend(args.backend), args.backend)
            print("=" * 72)
        except (FileNotFoundError, ValueError) as exc:
            print(f"Nincs használható token ({exc.__class__.__name__}) → "
                  "csak a helyi adatok.")
            print("=" * 72)

    _scan_local_results(os.path.join(_HERE, "results"))
    print("=" * 72)
    print("Értelmezés:")
    print("  • A `delay` τ-t fizikai időben (µs) kapja, a transzpiler a cél dt-jével")
    print("    konvertálja → a τ-tengely konverziója konzisztens.")
    print("  • A dt nominális, ezért a τ-tengely EMPIRIKUS referenduma a kontroll")
    print("    kar (csak T1-től függ): qds_axis_arbitration.py.")
    return 0


if __name__ == "__main__":
    from qds.cli import run

    sys.exit(run(main))
