import asyncio

import pytest

from pyfarm.control.engine.errors import ReplayExhausted
from pyfarm.control.sensors.replay import ReplaySensor, replay_sensors_from_rows


def test_replay_sensor_yields_in_order():
    s = ReplaySensor("temperature", [20.0, 21.0, 22.0], unit="celsius")
    values = [asyncio.run(s.read()).value for _ in range(3)]
    assert values == [20.0, 21.0, 22.0]


def test_replay_sensor_raises_when_exhausted():
    s = ReplaySensor("temperature", [20.0])
    asyncio.run(s.read())
    with pytest.raises(ReplayExhausted):
        asyncio.run(s.read())


def test_replay_sensor_loops():
    s = ReplaySensor("temperature", [1.0, 2.0], loop=True)
    values = [asyncio.run(s.read()).value for _ in range(4)]
    assert values == [1.0, 2.0, 1.0, 2.0]


def test_sensors_from_rows_one_per_column():
    rows = [
        {"timestamp": "t0", "temperature": "20", "humidity_rh": "0.9"},
        {"timestamp": "t1", "temperature": "21", "humidity_rh": "0.92"},
    ]
    sensors = {s.metric: s for s in replay_sensors_from_rows(rows)}
    assert set(sensors) == {"temperature", "humidity_rh"}
    assert asyncio.run(sensors["temperature"].read()).value == 20.0
