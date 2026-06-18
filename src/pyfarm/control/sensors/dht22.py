"""DHT22 temperature/humidity sensor.

The hardware backend is injectable so the module is safe to import on
non-Pi machines.  Pass a ``backend`` callable in tests; omit it in
production and the default will attempt to use ``adafruit_dht`` lazily.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable

from pyfarm.control.engine.context import SensorReading
from pyfarm.control.engine.errors import SensorReadError
from pyfarm.control.sensors.base import Sensor

# Backend returns (temperature_c, humidity_rh) or raises on error.
DHT22Backend = Callable[[], tuple[float, float]]


def _adafruit_backend(gpio: int) -> DHT22Backend:
    """Lazy-loaded adafruit_dht backend for real hardware."""
    try:
        import adafruit_dht  # type: ignore
        import board  # type: ignore
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "adafruit-circuitpython-dht not installed. "
            "Run: pip install adafruit-circuitpython-dht"
        ) from exc

    _PIN_MAP = {4: board.D4, 17: board.D17, 22: board.D22, 27: board.D27}
    pin = _PIN_MAP.get(gpio, board.D4)
    device = adafruit_dht.DHT22(pin)

    def read() -> tuple[float, float]:  # pragma: no cover
        temp = device.temperature
        rh = device.humidity
        if temp is None or rh is None:
            raise SensorReadError(f"DHT22 on gpio {gpio}: no reading")
        return float(temp), float(rh)

    return read


class DHT22TemperatureSensor(Sensor):
    """Reports temperature (°C) from a DHT22."""

    def __init__(self, gpio: int, *, backend: DHT22Backend | None = None) -> None:
        super().__init__("temperature", unit="celsius")
        self.gpio = gpio
        self._backend = backend

    def _resolve(self) -> DHT22Backend:
        if self._backend is None:
            self._backend = _adafruit_backend(self.gpio)
        return self._backend

    async def read(self) -> SensorReading:
        try:
            temp, _ = self._resolve()()
        except SensorReadError:
            raise
        except Exception as exc:
            raise SensorReadError(f"DHT22 read failed: {exc}") from exc
        return SensorReading(value=temp, unit="celsius", timestamp=datetime.now(timezone.utc))


class DHT22HumiditySensor(Sensor):
    """Reports relative humidity (0–100 %) from a DHT22."""

    def __init__(self, gpio: int, *, backend: DHT22Backend | None = None) -> None:
        super().__init__("humidity_rh", unit="percent")
        self.gpio = gpio
        self._backend = backend

    def _resolve(self) -> DHT22Backend:
        if self._backend is None:
            self._backend = _adafruit_backend(self.gpio)
        return self._backend

    async def read(self) -> SensorReading:
        try:
            _, rh = self._resolve()()
        except SensorReadError:
            raise
        except Exception as exc:
            raise SensorReadError(f"DHT22 read failed: {exc}") from exc
        return SensorReading(value=rh, unit="percent", timestamp=datetime.now(timezone.utc))
