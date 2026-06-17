"""Replay sensor tests — uses the new pyfarm.control.sensors.replay API."""

import asyncio

import pytest

from pyfarm.control.engine.errors import ReplayExhausted
from pyfarm.control.sensors.replay import ReplaySensor, replay_sensors_from_rows


def test_replay_sensor_reads_in_order():
    sensor = ReplaySensor("temperature", [18.2, 18.1, 17.9], unit="celsius")
    readings = [asyncio.run(sensor.read()) for _ in range(3)]
    assert [r.value for r in readings] == [18.2, 18.1, 17.9]
    assert sensor.exhausted


def test_replay_sensor_raises_when_exhausted():
    sensor = ReplaySensor("temperature", [20.0])
    asyncio.run(sensor.read())
    with pytest.raises(ReplayExhausted):
        asyncio.run(sensor.read())


def test_replay_sensor_holds_last_value_when_looping():
    sensor = ReplaySensor("temperature", [1.0, 2.0], loop=True)
    values = [asyncio.run(sensor.read()).value for _ in range(4)]
    assert values == [1.0, 2.0, 1.0, 2.0]


def test_sensors_from_rows_one_per_column():
    rows = [
        {"timestamp": "t0", "temperature": "20", "humidity_rh": "0.9"},
        {"timestamp": "t1", "temperature": "21", "humidity_rh": "0.92"},
    ]
    sensors = {s.metric: s for s in replay_sensors_from_rows(rows)}
    assert set(sensors) == {"temperature", "humidity_rh"}
    assert asyncio.run(sensors["temperature"].read()).value == 20.0
