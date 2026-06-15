"""An actuator that records what it *would* have done instead of touching
hardware. The other half of the replay onramp: pair with ``ReplaySensor`` to
run the full engine against recorded data and inspect the command log.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from pyfarm.control.actuators.base import Actuator, Command


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class LoggedCommand:
    timestamp: datetime
    command: Command


class LoggingActuator(Actuator):
    """Records every applied command. Only logs when the command changes the
    on/off state (so the log reads like ``would have fired misting at ...``),
    unless ``log_every`` is set."""

    def __init__(
        self,
        name: str,
        *,
        log_every: bool = False,
        clock: Callable[[], datetime] = _now,
    ) -> None:
        super().__init__(name)
        self.history: list[LoggedCommand] = []
        self._log_every = log_every
        self._clock = clock
        self._last_on: bool = False

    async def apply(self, command: Command) -> None:
        on = self.is_on(command)
        if self._log_every or on != self._last_on:
            self.history.append(LoggedCommand(self._clock(), command))
        self._last_on = on

    @property
    def transitions(self) -> list[LoggedCommand]:
        """State-change commands only (always recorded regardless of mode)."""
        result: list[LoggedCommand] = []
        last: bool = False
        for entry in self.history:
            on = self.is_on(entry.command)
            if on != last:
                result.append(entry)
            last = on
        return result
