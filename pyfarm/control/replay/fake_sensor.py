from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from pyfarm.core.models import SensorReading, Unit


class ReplaySensor:
    """
    Feeds pre-recorded readings from a CSV file, one row per tick.

    Expected CSV columns: timestamp (ISO 8601), plus one column per metric.
    Example header: timestamp,temperature,humidity_rh,co2_ppm
    """

    def __init__(self, path: str | Path, metric: str, unit: Unit = Unit.UNITLESS):
        self.metric = metric
        self.unit = unit
        self._rows: list[tuple[datetime, float]] = []
        self._index = 0
        self._load(Path(path))

    def _load(self, path: Path) -> None:
        with open(path, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                ts = datetime.fromisoformat(row["timestamp"])
                value = float(row[self.metric])
                self._rows.append((ts, value))
        if not self._rows:
            raise ValueError(f"ReplaySensor: no data found for metric '{self.metric}' in {path}")

    async def read(self) -> SensorReading:
        idx = min(self._index, len(self._rows) - 1)
        ts, value = self._rows[idx]
        if self._index < len(self._rows):
            self._index += 1
        return SensorReading(
            value=value, unit=self.unit, timestamp=ts, metric=self.metric
        )

    @property
    def exhausted(self) -> bool:
        return self._index >= len(self._rows)

    def __len__(self) -> int:
        return len(self._rows)
