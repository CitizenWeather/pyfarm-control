from __future__ import annotations

import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from itertools import islice
from typing import Any

from pyfarm.core.models import SensorReading, ActuatorState, ControlEvent, EventKind
from pyfarm.observability.event_bus import EventBus
from pyfarm.control.spec.schema import GrowSpec, Stage


@dataclass
class ActuatorOverride:
    """Temporary override for an actuator state."""
    actuator_id: str
    desired_state: bool
    applied_at: datetime
    expires_at: datetime
    reason: str | None = None


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
    overrides: dict[str, ActuatorOverride] = field(default_factory=dict)
    bus: EventBus | None = None

    @classmethod
    def new(cls, spec: GrowSpec) -> ControlContext:
        return cls(
            run_id=str(uuid.uuid4()),
            spec=spec,
            current_stage_index=0,
            stage_entered_at=datetime.now(timezone.utc),
        )

    @property
    def current_stage(self) -> Stage:
        return self.spec.stages[self.current_stage_index]

    def log(self, kind: EventKind, message: str, **data: Any) -> None:
        event = ControlEvent(kind=kind, message=message, data=data)
        self.events.append(event)
        if self.bus is not None:
            self.bus.emit(event)

    def apply_actuator_override(
        self, actuator_id: str, desired_state: bool, duration_seconds: int = 86400, reason: str | None = None
    ) -> ActuatorOverride:
        """Register an actuator override. Expires after duration_seconds (default 24h)."""
        now = datetime.now(timezone.utc)
        override = ActuatorOverride(
            actuator_id=actuator_id,
            desired_state=desired_state,
            applied_at=now,
            expires_at=now + timedelta(seconds=duration_seconds),
            reason=reason,
        )
        self.overrides[actuator_id] = override
        self.log(
            EventKind.SYSTEM,
            f"Actuator override registered: {actuator_id}={desired_state}",
            override_reason=reason,
            expires_in_seconds=duration_seconds,
        )
        return override

    def get_active_override(self, actuator_id: str) -> ActuatorOverride | None:
        """Get active override for actuator, or None if expired."""
        override = self.overrides.get(actuator_id)
        if override and datetime.now(timezone.utc) < override.expires_at:
            return override
        if override:
            del self.overrides[actuator_id]
        return None

    def to_status_dict(self) -> dict[str, Any]:
        """Serialisable snapshot for the HTTP status API."""
        stage = self.current_stage
        elapsed_days = (datetime.now(timezone.utc) - self.stage_entered_at).total_seconds() / 86400
        return {
            "run_id": self.run_id,
            "spec_name": self.spec.metadata.name,
            "current_stage": stage.name,
            "elapsed_days": round(elapsed_days, 4),
            "readings": {
                m: {"value": r.value, "unit": r.unit, "stale": r.stale}
                for m, r in self.readings.items()
            },
            "derived": dict(self.derived),
            "actuator_states": {
                n: {"state": s.state, "timestamp": s.timestamp.isoformat()}
                for n, s in self.actuator_states.items()
            },
            "recent_events": [
                {
                    "kind": e.kind,
                    "message": e.message,
                    "timestamp": e.timestamp.isoformat(),
                }
                for e in reversed(list(islice(reversed(self.events), 20)))
            ],
        }

    def as_flat_dict(self) -> dict[str, Any]:
        """Flat dict for expression evaluation — what variables are in scope."""
        flat: dict[str, Any] = {
            "stage": self.current_stage.name,
            "elapsed_days": (
                (datetime.now(timezone.utc) - self.stage_entered_at).total_seconds() / 86400
            ),
        }
        for metric, reading in self.readings.items():
            flat[metric] = {"current": reading.value, "stale": reading.stale}
        for k, v in self.derived.items():
            flat[k] = v
        # sensor sub-namespace for flatline detection etc.
        flat["sensor"] = {m: {"value": r.value} for m, r in self.readings.items()}
        return flat
