# -*- coding: utf-8 -*-
"""
QDS — a kontroll kar T1-illesztese: a TAU-TENGELY DONTBIRaja
==========================================================
A ket kar elteroen serul el a modelltől:
  - ECHO  gyorsabban hanylik, mint a kalibralt T2 mondja
  - KONTROLL lassabban hanylik, mint a kalibralt T1 mondja

Ha a hiba IDOZITESI (a QPU a beadott dt-t mas aranyban szamolta),
akkor a ket illesztett ertek AZONOS aranyban kellene eltolodnia
(T2_eff/T2 = T1_eff/T1), mert ugyanaz a rejtett idoskalaszorja.

Ha viszont T1 illeszkedik es a T2 nem, akkor az NEM idoskalaszor,
hanem valodi extra dekoherencia az echo karban (frekvencia-drift stb.).

Tehát: T1_eff/T1  ==  T2_eff/T2  ->  idoskala hiba
      T1_eff/T1 ~= 1  es T2_eff/T2 << 1  ->  valodi fizika
"""
import json, os

import numpy as np
from scipy.optimize import curve_fit

JOB_ID = 'dba0q2gc77vs738252kg'
TAUS = [0, 10, 25, 50, 100, 200, 400, 800]
T1_CAL = 254.1627621299776e-6
T2_CAL = 121.25600306875533e-6
THETA = 2.353304971691044

with open(os.path.join('results', f'qam_echo_{JOB_ID}.json'), encoding='utf-8') as f:
    rows = json.load(f)['rows']
echo = np.array([rows[2 * i]['p0'] for i in range(8)]) / 100
ctrl = np.array([rows[2 * i + 1]['p0'] for i in range(8)]) / 100
t = np.array(TAUS, dtype=float) * 1e-6
m = t > 0

c, s2 = np.cos(THETA), np.sin(THETA) ** 2


def ctrl_model(tt, t1, p0_off=0.0):
    return 0.5 + 0.5 * (1 + (c - 1) * np.exp(-tt / t1)) + p0_off


def echo_model(tt, t2, t1=T1_CAL):
    e1 = np.exp(-tt / t1)
    return 0.5 + 0.5 * (np.exp(-tt / t2) * s2 + e1 * c * c + c * (1 - e1))


print('=' * 74)
print('A) KONTROLL kar -> T1 illesztese (a tau-tengely arbitere)')
p1, cov1 = curve_fit(ctrl_model, t[m], ctrl[m], p0=[250e-6, 0.0],
                     bounds=([50e-6, -0.02], [1e-3, 0.02]))
e1 = np.sqrt(np.diag(cov1))
pred1 = ctrl_model(t[m], *p1) * 100
rms1 = float(np.sqrt(np.mean((ctrl[m] * 100 - pred1) ** 2)))
print(f'   T1_ill = {p1[0]*1e6:7.2f} +/- {e1[0]*1e6:.2f} us   '
      f'(offset {p1[1]*100:+.2f}%, RMS {rms1:.2f}%)')
r1 = p1[0] / T1_CAL
print(f'   T1_ill / T1_kalib = {r1:.3f}  +/- {e1[0]/T1_CAL:.3f}')

print('=' * 74)
print('B) ECHO kar -> T2 illesztese (T1 fixen a kalibralt értéken)')
p2, cov2 = curve_fit(echo_model, t[m], echo[m], p0=[150e-6],
                     bounds=([1e-8], [20e-3]))
e2 = float(np.sqrt(cov2[0][0]))
pred2 = echo_model(t[m], p2[0]) * 100
rms2 = float(np.sqrt(np.mean((echo[m] * 100 - pred2) ** 2)))
print(f'   T2_ill = {p2[0]*1e6:7.2f} +/- {e2*1e6:.2f} us   (RMS {rms2:.2f}%)')
r2 = p2[0] / T2_CAL
print(f'   T2_ill / T2_kalib = {r2:.3f}  +/- {e2/T2_CAL:.3f}')

print('=' * 74)
print('C) ITERAZIO: a ket kar JOTEGY KULON aranyt ad?')
print(f'   T1 arany = {r1:.3f}      T2 arany = {r2:.3f}')
print(f'   kulonbseg = {abs(r1-r2):.3f}   (a hibas valtozo szoraja ~ '
      f'{max(e1[0]/T1_CAL, e2/T2_CAL):.3f})')
if abs(r1 - r2) > 0.25:
    print('   -> NEM a rejtett idoskala: a ket kar kulonm ok miatt serul el.')
else:
    print('   -> osszhangzo eltolodas: a rejtett idoskcala gyanuja nyer.')
print('=' * 74)
print('D) RESZLETEZO KONTROLL-MODELL hatas vizsgalata')
print('   tau(us)  mert    modell(T1=kalib)  modell(T1=ill)  resztal-kulonbseg')
for i in range(8):
    mc = ctrl_model(t[i:i+1], T1_CAL)[0] * 100
    mf = ctrl_model(t[i:i+1], p1[0], p1[1])[0] * 100
    print(f'   {TAUS[i]:>6}  {ctrl[i]*100:6.2f}  {mc:>15.2f}  {mf:>14.2f}'
          f'  {ctrl[i]*100-mc:>+9.2f}')