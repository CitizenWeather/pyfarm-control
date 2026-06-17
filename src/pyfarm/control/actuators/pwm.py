"""PWM actuator for things that take a continuous 0..1 duty (e.g. a fan)."""

from __future__ import annotations

from typing import Callable

from pyfarm.control.actuators.base import Actuator, Command

# A backend writes a duty cycle (0..1) to a pin.
PwmBackend = Callable[[int, float], None]


class PwmActuator(Actuator):
    def __init__(
        self,
        name: str,
        gpio: int,
        *,
        backend: PwmBackend | None = None,
        frequency_hz: float = 1000.0,
    ) -> None:
        super().__init__(name)
        self.gpio = gpio
        self.frequency_hz = frequency_hz
        self._backend = backend
        self._duty = 0.0

    @property
    def duty(self) -> float:
        return self._duty

    async def apply(self, command: Command) -> None:
        if isinstance(command, bool):
            duty = 1.0 if command else 0.0
        else:
            duty = max(0.0, min(1.0, float(command)))
        if self._backend is None:
            raise RuntimeError(
                f"PwmActuator {self.name!r} has no backend; pass one explicitly."
            )
        self._backend(self.gpio, duty)
        self._duty = duty
