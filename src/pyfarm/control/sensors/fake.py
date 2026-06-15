"""In-memory sensors for tests, demos and the playground."""

from __future__ import annotations

from pyfarm.control.engine.context import SensorReading
from pyfarm.control.sensors.base import Sensor


class FakeSensor(Sensor):
    """A sensor whose value you set directly. Useful for unit tests."""

    def __init__(self, metric: str, value: float, unit: str = "") -> None:
        super().__init__(metric, unit)
        self.value = value

    def set(self, value: float) -> None:
        self.value = value

    async def read(self) -> SensorReading:
        return SensorReading(value=self.value, unit=self.unit)
