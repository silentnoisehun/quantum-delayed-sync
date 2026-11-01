"""Áramkör-építés és a sablon kanonikus hash-e.

A hash a **sablonból** készül, nem a job visszaadott ISA-áramköréből: a
Sampler nem teszi lekérdezhetővé a beküldött ISA-áramköröket. Azonos hash
tehát azt bizonyítja, hogy minden futás ugyanazt a fizikai láncot építette.

FIGYELEM: a ``circuit_hash`` kimenete **publikált adat**
(``results/circuit_hashes.json`` → ``054e9031…ff2c``). Ha bármit módosítasz a
hash számításán vagy a `build_circuits` áramkör-sorrendjén, a hash megváltozik
— ez nem hiba, de a régi futásokkal való összehasonlíthatóság megszűnik.
A `tests/test_template.py` ezt a reprodukálhatóságot ellenőrzi.
"""

import hashlib

from qds.constants import (
    DT_GRANULARITY,
    LAMBDA,
    PHI,
    TAUS_US,
    THETA,
)


def tau_to_dt(tau_us, dt, granularity=DT_GRANULARITY):
    """τ (µs) → dt-egység, a granularitásra (alapból 16) igazítva.

    Csak a szimulátor áramköreihez kell; a hardveres áramkör a τ-t
    **fizikai időben** (µs) adja meg, és a transzpiler konvertálja a cél
    backend dt-jével.
    """
    n = round(tau_us * 1e-6 / dt)
    return int(granularity * round(n / granularity))


def build_circuits(dt=None, unit="us", taus_us=TAUS_US, theta=THETA,
                   phi=PHI, lam=LAMBDA):
    """Felépíti a 8 τ-hoz tartozó echo és kontroll áramkört.

    Args:
        dt: a dt hossza másodpercben (csak ``unit='dt'`` esetén).
        unit: ``'dt'`` → a szimulátor (dt-re igazított mintaszám);
            ``'us'`` → a hardver (fizikai idő, a transzpiler konvertálja).
        taus_us: a τ-rács.
        theta, phi, lam: a random-axis U kapu szögei.

    Returns:
        list[tuple]: ``(tau_us, duration, echo_circuit, ctrl_circuit)``.
    """
    from qiskit import QuantumCircuit

    if unit not in ("dt", "us"):
        raise ValueError(f"ismeretlen unit: {unit!r} (csak 'dt' vagy 'us')")
    if unit == "dt" and not dt:
        raise ValueError("unit='dt' esetén a dt kötelező")

    out = []
    for tau in taus_us:
        dur = tau_to_dt(tau, dt) if unit == "dt" else tau
        qc_e = QuantumCircuit(1)
        qc_e.u(theta, phi, lam, 0)
        qc_e.barrier()
        if dur > 0:
            qc_e.delay(dur, 0, unit=unit)
        qc_e.barrier()
        qc_e.u(theta, phi, lam, 0).inverse()
        qc_e.barrier()
        qc_e.measure_all()

        qc_c = QuantumCircuit(1)
        qc_c.u(theta, phi, lam, 0)
        qc_c.barrier()
        if dur > 0:
            qc_c.delay(dur, 0, unit=unit)
        qc_c.barrier()
        qc_c.measure_all()
        out.append((tau, dur, qc_e, qc_c))
    return out


def circuit_hash(circuits):
    """A sablon kanonikus SHA-256 hash-e.

    Args:
        circuits: a :func:`build_circuits` kimenete.

    Returns:
        str: 64 karakteres hex SHA-256.
    """
    parts = []
    for tau, _dur, qc_e, qc_c in circuits:
        for arm, qc in (("echo", qc_e), ("ctrl", qc_c)):
            ops = [
                (inst.operation.name, str(inst.qubits), str(inst.operation.params))
                for inst in qc.data
            ]
            parts.append(f"{tau}|{arm}|" + ";".join(f"{n},{q},{p}" for n, q, p in ops))
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()


def template_hash():
    """A hardveres sablon (unit='us') hash-e — ez a publikált érték."""
    return circuit_hash(build_circuits(unit="us"))
