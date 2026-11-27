"""Pure diagnostic functions. Patterns are hypotheses, not safety limits."""
from dataclasses import dataclass
from .models import Reading, Settings, require_finite
from .refrigerants import saturation_temperature

PRESSURE_PATTERNS = {
    ('equal', 'above'): 'Possible expansion valve (TEV) issue',
    ('above', 'below'): 'High-side pressure above target; low-side below target',
    ('below', 'above'): 'Possible refrigerant leak or evaporator airflow issue (legacy rule; verify)',
    ('below', 'below'): 'Possible compressor inefficiency (legacy rule; verify)',
    ('above', 'above'): 'Possible condenser airflow issue',
    ('equal', 'equal'): 'No pressure deviation detected',
    ('below', 'equal'): 'Possible low-side restriction (legacy rule; verify)',
    ('equal', 'below'): 'Possible expansion valve overfeeding (legacy rule; verify)',
    ('above', 'equal'): 'Possible partial high-side issue',
}
CHARGE_PATTERNS = {
    ('high', 'low'): 'Possible undercharge or leak',
    ('low', 'high'): 'Possible overcharge or expansion valve issue',
    ('high', 'normal'): 'Possible metering restriction or airflow issue',
    ('high', 'high'): 'Possible liquid-line restriction',
    ('low', 'normal'): 'Possible floodback or overfeeding',
    ('normal', 'low'): 'Possible undercharge',
    ('normal', 'high'): 'Possible overcharge or condenser issue',
    ('normal', 'normal'): 'No charge-related deviation detected',
}


def classify_pressure(value: float, target: float, tolerance: float = 0.05) -> str:
    require_finite(value, target, tolerance)
    if tolerance < 0:
        raise ValueError('Tolerance must be nonnegative')
    if abs(value - target) <= abs(target) * tolerance:
        return 'equal'
    return 'above' if value > target else 'below'


def classify_temperature(value: float, target: float, tolerance: float = 2.0) -> str:
    require_finite(value, target, tolerance)
    if tolerance < 0:
        raise ValueError('Tolerance must be nonnegative')
    return 'low' if value < target - tolerance else 'high' if value > target + tolerance else 'normal'


@dataclass(frozen=True)
class Diagnosis:
    pressure_state: tuple[str, str]
    pressure_message: str
    superheat: float | None = None
    subcooling: float | None = None
    charge_state: tuple[str, str] | None = None
    charge_message: str | None = None

    @property
    def pressure_fault(self) -> bool:
        return self.pressure_state != ('equal', 'equal')


def diagnose(reading: Reading, settings: Settings) -> Diagnosis:
    state = (classify_pressure(reading.high_pressure, settings.high_setpoint, settings.pressure_tolerance),
             classify_pressure(reading.low_pressure, settings.low_setpoint, settings.pressure_tolerance))
    message = PRESSURE_PATTERNS[state]
    if settings.refrigerant is None:
        return Diagnosis(state, message)
    if reading.suction_temperature is None or reading.liquid_temperature is None:
        return Diagnosis(state, message, charge_message='Line temperature readings missing; charge assessment unavailable')
    evap = saturation_temperature(reading.low_pressure, settings.refrigerant, 'superheat')
    cond = saturation_temperature(reading.high_pressure, settings.refrigerant, 'subcooling')
    sh = None if evap is None else reading.suction_temperature - evap
    sc = None if cond is None else cond - reading.liquid_temperature
    if sh is None or sc is None:
        return Diagnosis(state, message, sh, sc, charge_message='Pressure outside PT table; charge assessment unavailable')
    charge_state = (classify_temperature(sh, settings.target_superheat, settings.temperature_tolerance),
                    classify_temperature(sc, settings.target_subcooling, settings.temperature_tolerance))
    return Diagnosis(state, message, sh, sc, charge_state,
                     CHARGE_PATTERNS.get(charge_state, 'Inconclusive charge pattern; manual inspection needed'))
