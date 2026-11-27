"""Typed data and validated configuration; all temperatures in °C."""
from dataclasses import dataclass
from math import isfinite
from .refrigerants import normalize_refrigerant


def require_finite(*values: float) -> None:
    if not all(isfinite(value) for value in values):
        raise ValueError('All measurements and targets must be finite')


@dataclass(frozen=True)
class Settings:
    high_setpoint: float
    low_setpoint: float
    refrigerant: str | None = None
    target_superheat: float | None = None
    target_subcooling: float | None = None
    pressure_tolerance: float = 0.05
    temperature_tolerance: float = 2.0
    consecutive_required: int = 3
    interval_seconds: float = 0.0

    def __post_init__(self):
        require_finite(self.high_setpoint, self.low_setpoint, self.pressure_tolerance,
                       self.temperature_tolerance, self.interval_seconds)
        if min(self.pressure_tolerance, self.temperature_tolerance, self.interval_seconds) < 0:
            raise ValueError('Tolerances and interval must be nonnegative')
        if type(self.consecutive_required) is not int or self.consecutive_required < 1:
            raise ValueError('Alarm threshold must be a positive integer')
        if self.refrigerant is None:
            if self.target_superheat is not None or self.target_subcooling is not None:
                raise ValueError('Temperature targets require a refrigerant')
        else:
            object.__setattr__(self, 'refrigerant', normalize_refrigerant(self.refrigerant))
            if self.target_superheat is None or self.target_subcooling is None:
                raise ValueError('Both temperature targets are required')
            require_finite(self.target_superheat, self.target_subcooling)


@dataclass(frozen=True)
class Reading:
    high_pressure: float
    low_pressure: float
    suction_temperature: float | None = None
    liquid_temperature: float | None = None

    def __post_init__(self):
        require_finite(self.high_pressure, self.low_pressure)
        require_finite(*(v for v in (self.suction_temperature, self.liquid_temperature) if v is not None))
