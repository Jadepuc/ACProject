"""Original project PT data (°C, presumed bar gauge); not independently validated."""
from bisect import bisect_left
from math import isfinite

TEMPERATURES = (-40.0, -34.4, -28.9, -23.3, -17.8, -12.2, -6.7, -1.1, 4.4, 10.0, 15.6, 21.1, 26.7, 32.2, 37.8, 43.3, 48.9, 54.4, 60.0, 65.6)

PRESSURES = {
    'R410A': {'single': (0.74, 1.22, 1.81, 2.5, 3.32, 4.29, 5.41, 6.69, 8.16, 9.83, 11.73, 13.87, 16.25, 18.93, 21.9, 25.19, 28.84, 32.87, 37.34, 42.26)},
    'R22': {'single': (0.04, 0.34, 0.7, 1.14, 1.65, 2.26, 2.97, 3.79, 4.73, 5.8, 7.01, 8.37, 9.9, 11.61, 13.51, 15.61, 17.93, 20.47, 23.26, 26.32)},
    'R134A': {'single': (-0.5, -0.33, -0.12, 0.13, 0.45, 0.82, 1.27, 1.8, 2.41, 3.13, 3.96, 4.9, 5.98, 7.19, 8.56, 10.09, 11.8, 13.7, 15.8, 18.13)},
    'R404A': {
        'bubble': (0.34, 0.71, 1.16, 1.7, 2.32, 3.05, 3.9, 4.87, 5.99, 7.26, 8.69, 10.29, 12.09, 14.1, 16.33, 18.8, 21.52, 24.52, 27.83, 31.5),
        'dew': (0.3, 0.66, 1.1, 1.63, 2.25, 2.97, 3.81, 4.78, 5.89, 7.14, 8.56, 10.16, 11.96, 13.95, 16.18, 18.64, 21.37, 24.38, 27.7, 31.37),
    },
}

def normalize_refrigerant(name: str) -> str:
    key = ''.join(name.upper().replace('-', '').split())
    if key not in PRESSURES:
        raise ValueError(f'Unsupported refrigerant: {name}')
    return key


def saturation_temperature(pressure: float, refrigerant: str, purpose: str) -> float | None:
    """Interpolate within the source table; never extrapolate."""
    if not isfinite(pressure):
        raise ValueError('Pressure must be finite')
    if purpose not in ('superheat', 'subcooling'):
        raise ValueError('Unknown calculation purpose')
    curves = PRESSURES[normalize_refrigerant(refrigerant)]
    pressures = curves['single'] if 'single' in curves else curves['dew' if purpose == 'superheat' else 'bubble']
    if not pressures[0] <= pressure <= pressures[-1]:
        return None
    i = bisect_left(pressures, pressure)
    if pressures[i] == pressure:
        return TEMPERATURES[i]
    p0, p1 = pressures[i - 1:i + 1]
    t0, t1 = TEMPERATURES[i - 1:i + 1]
    return t0 + (pressure - p0) * (t1 - t0) / (p1 - p0)
