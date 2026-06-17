"""Sensor abstraction. Real and simulated sensors implement the same interface
so the runner is agnostic to where readings come from."""

from __future__ import annotations

import abc

from pyfarm.control.engine.context import SensorReading


class Sensor(abc.ABC):
    """A source of readings for a single metric (e.g. ``temperature``)."""

    def __init__(self, metric: str, unit: str = "") -> None:
        self.metric = metric
        self.unit = unit

    @abc.abstractmethod
    async def read(self) -> SensorReading:
        """Return the current reading, or raise
        :class:`pyfarm.control.engine.errors.SensorReadError`."""
        raise NotImplementedError
