"""A small PID controller producing a 0..1 duty for PWM-driven actuators."""

from __future__ import annotations

from typing import Literal

from pyfarm.control.controllers.base import Controller
from pyfarm.control.engine.context import ControlContext

Direction = Literal["raise", "lower"]


class PidController(Controller):
    def __init__(
        self,
        metric: str,
        direction: Direction = "raise",
        *,
        kp: float = 1.0,
        ki: float = 0.0,
        kd: float = 0.0,
        dt: float = 1.0,
        output_limits: tuple[float, float] = (0.0, 1.0),
    ) -> None:
        self.metric = metric
        self.direction = direction
        self.kp, self.ki, self.kd = kp, ki, kd
        self.dt = dt
        self._lo, self._hi = output_limits
        self._integral = 0.0
        self._prev_error: float | None = None

    def reset(self) -> None:
        self._integral = 0.0
        self._prev_error = None

    def compute(self, ctx: ControlContext) -> float:
        reading = ctx.readings.get(self.metric)
        setpoint = self.setpoint(ctx)
        if reading is None or setpoint is None:
            return self._lo

        error = setpoint.target - reading.value
        if self.direction == "lower":
            error = -error

        self._integral += error * self.dt
        derivative = 0.0
        if self._prev_error is not None:
            derivative = (error - self._prev_error) / self.dt
        self._prev_error = error

        output = self.kp * error + self.ki * self._integral + self.kd * derivative
        # Anti-windup: clamp and back off the integral when saturated.
        clamped = max(self._lo, min(self._hi, output))
        if clamped != output and self.ki:
            self._integral -= error * self.dt
        return clamped
