import asyncio
import csv
import os
import tempfile
from pathlib import Path

import pytest

from pyfarm.control.replay.fake_sensor import ReplaySensor
from pyfarm.core.models import Unit


def _write_csv(path: Path, rows: list[dict]) -> None:
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


@pytest.fixture
def sensor_csv(tmp_path):
    p = tmp_path / "data.csv"
    _write_csv(p, [
        {"timestamp": "2024-01-15T08:00:00", "temperature": "18.2", "humidity_rh": "0.93", "co2_ppm": "810"},
        {"timestamp": "2024-01-15T08:00:10", "temperature": "18.1", "humidity_rh": "0.94", "co2_ppm": "805"},
        {"timestamp": "2024-01-15T08:00:20", "temperature": "17.9", "humidity_rh": "0.95", "co2_ppm": "790"},
    ])
    return p


def test_replay_sensor_reads_in_order(sensor_csv):
    sensor = ReplaySensor(sensor_csv, metric="temperature", unit=Unit.CELSIUS)
    assert len(sensor) == 3

    readings = [asyncio.run(sensor.read()) for _ in range(3)]
    assert [r.value for r in readings] == [18.2, 18.1, 17.9]
    assert sensor.exhausted


def test_replay_sensor_holds_last_value(sensor_csv):
    sensor = ReplaySensor(sensor_csv, metric="temperature", unit=Unit.CELSIUS)
    # exhaust
    for _ in range(3):
        asyncio.run(sensor.read())
    # should return last value indefinitely
    r = asyncio.run(sensor.read())
    assert r.value == 17.9
