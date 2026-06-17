"""GPIO relay actuator.

The hardware backend is injected so the engine stays testable and import-safe
on machines without ``RPi.GPIO``. On a Pi, pass a backend that drives the pin;
in tests/replay, use :class:`pyfarm.control.actuators.logging.LoggingActuator`
instead, or inject a recording callable here.
"""

from __future__ import annotations

from typing import Callable

from pyfarm.control.actuators.base import Actuator, Command

# A backend writes a boolean level to a GPIO pin.
GpioBackend = Callable[[int, bool], None]


def _default_backend() -> GpioBackend:
    """Best-effort RPi.GPIO backend. Imported lazily so importing this module
    never requires the library."""
    try:
        import RPi.GPIO as GPIO  # type: ignore
    except Exception as exc:  # pragma: no cover - hardware-only path
        raise RuntimeError(
            "No GPIO backend available. Install RPi.GPIO or pass an explicit "
            "backend to RelayActuator(...)."
        ) from exc

    GPIO.setmode(GPIO.BCM)  # pragma: no cover

    def write(pin: int, level: bool) -> None:  # pragma: no cover
        GPIO.setup(pin, GPIO.OUT)
        GPIO.output(pin, GPIO.HIGH if level else GPIO.LOW)

    return write


class RelayActuator(Actuator):
    def __init__(
        self,
        name: str,
        gpio: int,
        *,
        backend: GpioBackend | None = None,
        active_high: bool = True,
    ) -> None:
        super().__init__(name)
        self.gpio = gpio
        self._active_high = active_high
        self._backend = backend
        self._state = False

    @property
    def state(self) -> bool:
        return self._state

    def _resolve_backend(self) -> GpioBackend:
        if self._backend is None:
            self._backend = _default_backend()
        return self._backend

    async def apply(self, command: Command) -> None:
        on = self.is_on(command)
        level = on if self._active_high else not on
        self._resolve_backend()(self.gpio, level)
        self._state = on
