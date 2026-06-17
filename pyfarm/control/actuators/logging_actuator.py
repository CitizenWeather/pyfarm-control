from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from .base import BaseActuator


@dataclass
class ActuatorLogEntry:
    name: str
    action: str  # "on" | "off"
    timestamp: datetime


class LoggingActuator(BaseActuator):
    """
    Records what it would have done. No hardware required.
    Use this for replay runs, CI, and contributor onboarding.
    """

    def __init__(self, name: str, verbose: bool = True):
        super().__init__(name)
        self.log: list[ActuatorLogEntry] = []
        self.verbose = verbose

    async def on(self) -> None:
        self._record("on")

    async def off(self) -> None:
        self._record("off")

    def _record(self, action: str) -> None:
        # Deduplicate consecutive identical states
        if self.log and self.log[-1].action == action:
            return
        entry = ActuatorLogEntry(name=self.name, action=action, timestamp=datetime.utcnow())
        self.log.append(entry)
        if self.verbose:
            print(f"[{entry.timestamp.isoformat()}] actuator:{self.name} -> {action}")

    @property
    def current_state(self) -> str | None:
        return self.log[-1].action if self.log else None
