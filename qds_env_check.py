# -*- coding: utf-8 -*-
"""QDS — helyi ellenorzes (kvota nelkul): verziok, config, delay transpile."""
import json, os

import qiskit, qiskit_ibm_runtime
print('qiskit', qiskit.__version__, '| runtime', qiskit_ibm_runtime.__version__)
print('aer', __import__('qiskit_aer').__version__)

with open('ibm_token.json', encoding='utf-8') as f:
    token = json.load(f)['apikey']

svc = qiskit_ibm_runtime.QiskitRuntimeService(
    channel='ibm_quantum_platform', token=token, instance='auto')
b = svc.backend(name='ibm_kingston')

try:
    c = b.configuration()
    print('configuration().dt =', c.dt)
    print('timing_constraints =', getattr(c, 'timing_constraints', None))
except Exception as e:  # noqa: BLE001
    print('configuration() hiba:', type(e).__name__, e)

print('target.dt =', b.target.dt,
      '| granularity =', b.target.granularity,
      '| pulse_alignment =', b.target.pulse_alignment)

# --- delay unit konverzio a target alapjan --------------------------------
from qiskit import QuantumCircuit, transpile
for tau in (1, 10, 800):
    qc = QuantumCircuit(1)
    qc.x(0)
    qc.delay(tau, 0, unit='us')
    qc.measure_all()
    t = transpile(qc, b, optimization_level=0, initial_layout=[91])
    for inst in t.data:
        if inst.operation.name == 'delay':
            dt_used = b.target.dt
            print(f'  tau={tau:>4} us -> delay {inst.operation.duration} '
                  f'{inst.operation.unit}  (= {inst.operation.duration*dt_used*1e6:.2f} us '
                  f'ha dt={dt_used*1e9:.1f} ns)')

# --- u() elerheto-e qiskit 2.x-ben? ----------------------------------------
qc2 = QuantumCircuit(1)
try:
    qc2.u(0.3, 0.4, 0.5, 0)
    g = qc2.data[0].operation
    print('qc.u OK ->', g.name, '| inverse() ->', g.inverse().name)
except Exception as e:  # noqa: BLE001
    print('qc.u hiba:', type(e).__name__, e)