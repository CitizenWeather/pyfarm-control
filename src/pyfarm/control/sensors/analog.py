"""Generic analog sensor via injectable ADC backend.

Useful for any 0-3.3 V analogue signal routed through an ADC such as the
MCP3008.  Scale and offset convert raw 0–1 ADC values to engineering units.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable

from pyfarm.control.engine.context import SensorReading
from pyfarm.control.engine.errors import SensorReadError
from pyfarm.control.sensors.base import Sensor

# Backend returns a raw reading in [0, 1].
ADCBackend = Callable[[], float]


class AnalogSensor(Sensor):
    """Read an analogue channel and convert to engineering units.

    Args:
        metric: Metric name (e.g. ``"co2_ppm"``).
        unit: Engineering unit label (e.g. ``"ppm"``).
        backend: Callable returning a raw ADC value in ``[0, 1]``.
        scale: Multiply raw value by this to get engineering units.
        offset: Add this after scaling.

    Example — MCP3008 CO₂ sensor scaled to 0–5000 ppm::

        from pyfarm.control.sensors.analog import AnalogSensor

        def mcp3008_ch0() -> float:
            import busio, digitalio, board
            import adafruit_mcp3xxx.mcp3008 as MCP
            from adafruit_mcp3xxx.analog_in import AnalogIn
            spi = busio.SPI(clock=board.SCK, MISO=board.MISO, MOSI=board.MOSI)
            cs  = digitalio.DigitalInOut(board.CE0)
            mcp = MCP.MCP3008(spi, cs)
            return AnalogIn(mcp, MCP.P0).voltage / 3.3

        co2 = AnalogSensor("co2_ppm", "ppm", backend=mcp3008_ch0, scale=5000)
    """

    def __init__(
        self,
        metric: str,
        unit: str,
        *,
        backend: ADCBackend,
        scale: float = 1.0,
        offset: float = 0.0,
    ) -> None:
        super().__init__(metric, unit=unit)
        self._backend = backend
        self.scale = scale
        self.offset = offset

    async def read(self) -> SensorReading:
        try:
            raw = self._backend()
        except Exception as exc:
            raise SensorReadError(f"Analog sensor {self.metric!r} read failed: {exc}") from exc
        value = raw * self.scale + self.offset
        return SensorReading(value=value, unit=self.unit, timestamp=datetime.now(timezone.utc))
