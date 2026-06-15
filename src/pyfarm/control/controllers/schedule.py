"""Time-pattern controllers: photoperiod lighting and periodic duty cycling.

Two construction paths:

* :class:`ScheduleController` with ``on_seconds``/``period_seconds`` — a simple
  duty cycle (e.g. exhaust fan 5 min every hour).
* :meth:`ScheduleController.for_light` — reads the current stage's
  ``setpoints.light.schedule`` ("12/12") and drives a 24h photoperiod.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Callable

from pyfarm.control.controllers.base import Controller
from pyfarm.control.engine.context import ControlContext

_SCHEDULE_RE = re.compile(r"^(\d{1,2})/(\d{1,2})$")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _seconds_since_midnight(now: datetime) -> float:
    return now.hour * 3600 + now.minute * 60 + now.second + now.microsecond / 1e6


class ScheduleController(Controller):
    metric = None

    def __init__(
        self,
        on_seconds: float,
        period_seconds: float,
        *,
        clock: Callable[[], datetime] = _now,
        align_to_midnight: bool = True,
    ) -> None:
        if period_seconds <= 0:
            raise ValueError("period_seconds must be > 0")
        self.on_seconds = max(0.0, on_seconds)
        self.period_seconds = period_seconds
        self._clock = clock
        self._align = align_to_midnight

    @classmethod
    def for_light(cls, clock: Callable[[], datetime] = _now) -> "ScheduleController":
        """A photoperiod controller that reads the active stage's light schedule
        on every :meth:`compute`."""
        return _LightController(clock=clock)

    def _offset_seconds(self) -> float:
        now = self._clock()
        if self._align:
            return _seconds_since_midnight(now) % self.period_seconds
        return now.timestamp() % self.period_seconds

    def compute(self, ctx: ControlContext) -> bool:
        return self._offset_seconds() < self.on_seconds


class _LightController(ScheduleController):
    def __init__(self, clock: Callable[[], datetime] = _now) -> None:
        super().__init__(on_seconds=0, period_seconds=24 * 3600, clock=clock)

    def compute(self, ctx: ControlContext) -> bool:
        light = ctx.current_stage.setpoints.light
        match = _SCHEDULE_RE.match(light.schedule)
        hours_on = int(match.group(1)) if match else 0
        self.on_seconds = hours_on * 3600
        return _seconds_since_midnight(self._clock()) < self.on_seconds
