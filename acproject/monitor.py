"""Stateful alarm tracking, independent of sensors, CLI and logging."""
from dataclasses import dataclass
from .diagnostics import Diagnosis, diagnose
from .models import Reading, Settings


@dataclass
class AlarmTracker:
    required: int = 3
    last_state: tuple[str, str] | None = None
    count: int = 0

    def __post_init__(self):
        if type(self.required) is not int or self.required < 1:
            raise ValueError('Alarm threshold must be a positive integer')

    def update(self, result: Diagnosis) -> bool:
        """True once when a persistent pressure pattern reaches its threshold."""
        if not result.pressure_fault:
            self.last_state, self.count = None, 0
            return False
        self.count = self.count + 1 if self.last_state == result.pressure_state else 1
        self.last_state = result.pressure_state
        return self.count == self.required


class Monitor:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.alarms = AlarmTracker(settings.consecutive_required)

    def process(self, reading: Reading) -> tuple[Diagnosis, bool]:
        result = diagnose(reading, self.settings)
        return result, self.alarms.update(result)
