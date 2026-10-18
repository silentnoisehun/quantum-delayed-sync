# -*- coding: utf-8 -*-
"""
QDS — kimutathato-e a drift a szorason MERESI ZAJHOZ kepest?
===========================================================
A kerdes: a futasonkenti T2_eff szoras (39.2 us) tenyleges fizikai
ingadozas, vagy csak a shot noise terjedese?

Teszt: ha a futasok kozott a kulonbseg csak a Binning lenne, akkor a
futasonkenti szoras ~= az atlagos, futasonkENTI illesztési hiba (~10.8 us).
A szokasos chi2 teszt ezt ellenorzi:

  chi2 = sum (x_i - mean)^2 / sigma_i^2     sigma_i = a futas illesztési hibaja

N df (=4) alatt a nulla elosulas tortelmezett. A szamolt chi2 osszehasonlithato
a nulla atlagaval (=N).
"""
import numpy as np
from scipy import stats

t2 = np.array([77.5, 43.1, 140.8, 117.7, 69.1])       # us, futasonkent
se = np.array([12.9, 9.0, 10.7, 12.5, 9.0])          # us, futasonkenti illesztési hiba

n = len(t2)
mean = t2.mean()
sd = t2.std(ddof=1)
sem = sd / np.sqrt(n)
avg_se = se.mean()

print('=' * 72)
print('A FIVE FUTAS T2_eff')
for i in range(n):
    print(f'  run{i+1}: {t2[i]:6.1f} +- {se[i]:4.1f} us')
print(f'  atlag  : {mean:.1f} us   szoras {sd:.1f} us   SEM {sem:.1f} us')
print()
print(f'HA csak shot noise lenne, a futasonkenti szoras ~= {avg_se:.1f} us')
print(f'A MERT futasonkenti szoras                       = {sd:.1f} us')
print(f'  -> arany = {sd/avg_se:.2f}x')
print()

chi2 = np.sum((t2 - mean) ** 2 / se ** 2)
df = n - 1
p = 1 - stats.chi2.cdf(chi2, df)
print(f'chi2 = {chi2:.1f}   df = {df}   (nulla atlag = {df})')
print(f'p(nulla) = {p:.3e}   -> {"AZ INGADAS NEM VEHET SZAMITOTT ZAJBOL" if p < 0.01 else "nem eldonto"}')
print()
print('=' * 72)
print('AZ ECHO ES A KONTROLL KAR OSSZEHASONLITASA (melyik szektor instabil?)')
print('  Kontroll kar (csak T1) : atlag 273.8 us, szoras 37.2 us')
print('  Echo kar     (T2)      : atlag  89.6 us, szoras 39.2 us')
print(f'  Kalman arany: {37.2/39.2:.2f}')
print()
print('Ha a ZAJ altalaban okozott hiba lenne, a ket kar szorasa')
print('HOZAMERO aranyos lenne. A kalman arany 0.95 -> a ket kar')
print('szorasa gyakorlatilag AZONOS: a hiba nem a kartol fugg.')
print('=> A CSILLAPODAS MEREKOREGULAJASHOZ KOTOTT, nem a relaxaciohoz.')