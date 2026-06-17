from __future__ import annotations

import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from pyfarm.core.models import SensorReading, ActuatorState, ControlEvent, EventKind
from pyfarm.control.spec.schema import GrowSpec, Stage


@dataclass
class ControlContext:
    """
    Live state of a running grow.
    Sensors write here; controllers and alert evaluators read from here.
    Serialisable to disk for crash recovery.
    """

    run_id: str
    spec: GrowSpec
    current_stage_index: int
    stage_entered_at: datetime
    readings: dict[str, SensorReading] = field(default_factory=dict)
    derived: dict[str, float] = field(default_factory=dict)
    actuator_states: dict[str, ActuatorState] = field(default_factory=dict)
    events: deque[ControlEvent] = field(default_factory=lambda: deque(maxlen=1000))

    @classmethod
    def new(cls, spec: GrowSpec) -> ControlContext:
        return cls(
            run_id=str(uuid.uuid4()),
            spec=spec,
            current_stage_index=0,
            stage_entered_at=datetime.utcnow(),
        )

    @property
    def current_stage(self) -> Stage:
        return self.spec.stages[self.current_stage_index]

    def log(self, kind: EventKind, message: str, **data: Any) -> None:
        self.events.append(ControlEvent(kind=kind, message=message, data=data))

    def as_flat_dict(self) -> dict[str, Any]:
        """Flat dict for expression evaluation — what variables are in scope."""
        flat: dict[str, Any] = {
            "stage": self.current_stage.name,
            "elapsed_days": (
                (datetime.utcnow() - self.stage_entered_at).total_seconds() / 86400
            ),
        }
        for metric, reading in self.readings.items():
            flat[metric] = {"current": reading.value, "stale": reading.stale}
        for k, v in self.derived.items():
            flat[k] = v
        # sensor sub-namespace for flatline detection etc.
        flat["sensor"] = {m: {"value": r.value} for m, r in self.readings.items()}
        return flat
