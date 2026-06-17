"""Replay sensors: drive the full control loop from recorded data.

A contributor with no hardware can run the engine against a CSV of
temperature/humidity/CO2 readings and see exactly what it would have done.
This is also how deterministic integration tests are written.
"""

from __future__ import annotations

import csv
from collections.abc import Iterable, Sequence
from pathlib import Path

from pyfarm.control.engine.context import SensorReading
from pyfarm.control.engine.errors import ReplayExhausted
from pyfarm.control.sensors.base import Sensor


class ReplaySensor(Sensor):
    """Yields a pre-recorded sequence of values, one per :meth:`read`.

    When ``loop`` is false (the default), :meth:`read` raises
    :class:`ReplayExhausted` once the sequence is consumed, which the runner
    uses as a natural end-of-scenario signal.
    """

    def __init__(
        self,
        metric: str,
        values: Sequence[float],
        unit: str = "",
        *,
        loop: bool = False,
    ) -> None:
        super().__init__(metric, unit)
        self._values = list(values)
        self._loop = loop
        self._index = 0

    @property
    def exhausted(self) -> bool:
        return not self._loop and self._index >= len(self._values)

    async def read(self) -> SensorReading:
        if not self._values:
            raise ReplayExhausted(f"replay sensor {self.metric!r} has no data")
        if self._index >= len(self._values):
            if not self._loop:
                raise ReplayExhausted(
                    f"replay sensor {self.metric!r} exhausted after "
                    f"{len(self._values)} samples"
                )
            self._index = 0
        value = self._values[self._index]
        self._index += 1
        return SensorReading(value=value, unit=self.unit)


def replay_sensors_from_rows(
    rows: Iterable[dict[str, str]],
    units: dict[str, str] | None = None,
) -> list[ReplaySensor]:
    """Build one :class:`ReplaySensor` per column from an iterable of row dicts.

    Columns named ``timestamp``/``time``/``ts`` are ignored. Empty cells are
    skipped for that column's series.
    """
    units = units or {}
    series: dict[str, list[float]] = {}
    ignored = {"timestamp", "time", "ts", "datetime"}
    for row in rows:
        for key, raw in row.items():
            if key is None or key.lower() in ignored or raw in (None, ""):
                continue
            series.setdefault(key, []).append(float(raw))
    return [
        ReplaySensor(metric, values, unit=units.get(metric, ""))
        for metric, values in series.items()
    ]


def replay_sensors_from_csv(
    path: str | Path,
    units: dict[str, str] | None = None,
) -> list[ReplaySensor]:
    """Build replay sensors from a CSV whose header names the metrics."""
    with Path(path).open(newline="") as handle:
        return replay_sensors_from_rows(csv.DictReader(handle), units=units)
