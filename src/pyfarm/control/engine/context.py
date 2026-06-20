"""The live state of a running grow.

Sensors write readings here; controllers and the alert evaluator read from
here. The context is intentionally a plain dataclass so it can be snapshotted
to disk for crash recovery (see :mod:`pyfarm.control.engine.store`).
"""

from __future__ import annotations

import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Deque

# The value types are owned by pyfarm-core so drivers, persistence and the
# status API all speak the same types. Re-exported here for backwards
# compatibility with the many modules that import them from this location.
from pyfarm.core.models import ActuatorState, ControlEvent, SensorReading
from pyfarm.control.spec.schema import GrowSpec, Stage

__all__ = [
    "SensorReading",
    "ActuatorState",
    "ControlEvent",
    "ControlContext",
]


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class ControlContext:
    run_id: str
    spec: GrowSpec
    current_stage_index: int = 0
    stage_entered_at: datetime = field(default_factory=_now)

    readings: dict[str, SensorReading] = field(default_factory=dict)
    derived: dict[str, float] = field(default_factory=dict)
    # Manually logged / vision-derived observations, keyed by dotted metric,
    # e.g. {"visual.colonisation_pct": 0.97, "visual.pins_count": 12}.
    manual: dict[str, float | str] = field(default_factory=dict)

    actuator_states: dict[str, ActuatorState] = field(default_factory=dict)
    events: Deque[ControlEvent] = field(default_factory=lambda: deque(maxlen=1000))

    # Bookkeeping for flatline detection: when each metric's value last moved.
    _value_changed_at: dict[str, datetime] = field(default_factory=dict)

    @classmethod
    def new(cls, spec: GrowSpec, run_id: str | None = None) -> "ControlContext":
        return cls(run_id=run_id or uuid.uuid4().hex, spec=spec)

    @property
    def current_stage(self) -> Stage:
        return self.spec.stages[self.current_stage_index]

    @property
    def is_final_stage(self) -> bool:
        return self.current_stage_index >= len(self.spec.stages) - 1

    def record_reading(self, metric: str, reading: SensorReading) -> None:
        previous = self.readings.get(metric)
        if previous is None or previous.value != reading.value:
            self._value_changed_at[metric] = reading.timestamp
        self.readings[metric] = reading

    def log_event(self, kind: str, message: str, **data: Any) -> ControlEvent:
        event = ControlEvent(kind=kind, message=message, data=data)
        self.events.append(event)
        return event

    def get_metric(self, dotted: str) -> Any:
        """Resolve a dotted metric (e.g. ``visual.pins_count``) across readings,
        derived metrics and manual logs. Returns ``None`` if unknown."""
        flat = self.as_flat_dict()
        value: Any = flat
        for part in dotted.split("."):
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                return None
        return value

    def as_flat_dict(self, now: datetime | None = None) -> dict[str, Any]:
        """Build the nested namespace expressions are evaluated against.

        Produces ``temperature.current``, ``humidity_rh.current``,
        ``vpd.current``, ``stage``, ``sensor.<metric>.{current,flatline_minutes}``
        and any dotted manual metrics.
        """
        now = now or _now()
        flat: dict[str, Any] = {}

        for metric, reading in self.readings.items():
            flat.setdefault(metric, {})["current"] = reading.value

        for key, value in self.derived.items():
            flat.setdefault(key, {})["current"] = value

        sensor: dict[str, Any] = {}
        for metric, reading in self.readings.items():
            changed_at = self._value_changed_at.get(metric, reading.timestamp)
            sensor[metric] = {
                "current": reading.value,
                "flatline_minutes": reading.flatline_minutes(
                    value_changed_at=changed_at, now=now
                ),
            }
        flat["sensor"] = sensor

        for dotted, value in self.manual.items():
            target = flat
            parts = dotted.split(".")
            for part in parts[:-1]:
                target = target.setdefault(part, {})
            target[parts[-1]] = value

        flat["stage"] = self.current_stage.name
        return flat
