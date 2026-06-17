"""Actuator safety limits: minimum off-time and maximum on-time.

These are the tiny rules every grower knows — don't short-cycle the pump,
don't let the heater run away. The runner consults a guard after the
controller and interlock have spoken, and the guard has the final say.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable

from pyfarm.control.actuators.base import Actuator
from pyfarm.control.engine.context import ActuatorState
from pyfarm.control.spec.schema import ActuatorSafety


def _now() -> datetime:
    return datetime.now(timezone.utc)


class SafetyGuard:
    def __init__(self, *, clock: Callable[[], datetime] = _now) -> None:
        self._clock = clock

    def constrain(
        self,
        desired_on: bool,
        state: ActuatorState,
        safety: ActuatorSafety,
    ) -> tuple[bool, str | None]:
        """Return ``(allowed_on, reason_if_changed)`` after applying limits."""
        now = self._clock()
        seconds_in_state = state.seconds_in_state(now)

        max_on = self._max_on_seconds(safety)
        if state.on and max_on is not None and seconds_in_state >= max_on:
            return False, f"max on-time {max_on:.0f}s reached"

        if desired_on and not state.on and safety.min_off_seconds is not None:
            if seconds_in_state < safety.min_off_seconds:
                return False, (
                    f"min off-time {safety.min_off_seconds}s not met "
                    f"({seconds_in_state:.0f}s elapsed)"
                )
        return desired_on, None

    @staticmethod
    def _max_on_seconds(safety: ActuatorSafety) -> float | None:
        limits = []
        if safety.max_on_seconds is not None:
            limits.append(float(safety.max_on_seconds))
        if safety.max_on_minutes is not None:
            limits.append(safety.max_on_minutes * 60.0)
        return min(limits) if limits else None
