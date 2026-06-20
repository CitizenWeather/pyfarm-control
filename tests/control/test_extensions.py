"""Tests for the spec -> live-object factories in extensions.py."""

from __future__ import annotations

import asyncio

import pytest

from pyfarm.control.extensions import build_sensor
from pyfarm.control.sensors.dht22 import DHT22HumiditySensor, DHT22TemperatureSensor
from pyfarm.control.sensors.fake import FakeSensor
from pyfarm.control.sensors.replay import ReplaySensor
from pyfarm.control.spec.schema import SensorSpec


def test_build_dht22_temp_and_humidity():
    t = build_sensor("t", SensorSpec(kind="dht22_temp", metric="temperature", gpio=4))
    h = build_sensor("h", SensorSpec(kind="dht22_humidity", metric="humidity_rh", gpio=4))
    assert isinstance(t, DHT22TemperatureSensor)
    assert isinstance(h, DHT22HumiditySensor)


def test_build_fake_reads_constant():
    s = build_sensor("f", SensorSpec(kind="fake", metric="temperature", unit="celsius", value=21.0))
    assert isinstance(s, FakeSensor)
    reading = asyncio.run(s.read())
    assert reading.value == 21.0
    assert reading.unit == "celsius"


def test_build_replay_from_csv(tmp_path):
    csv = tmp_path / "data.csv"
    csv.write_text("temperature,humidity_rh\n19.0,0.9\n20.0,0.91\n")
    s = build_sensor(
        "r",
        SensorSpec(kind="replay", metric="temperature", unit="celsius", csv=str(csv)),
    )
    assert isinstance(s, ReplaySensor)
    assert asyncio.run(s.read()).value == 19.0
    assert asyncio.run(s.read()).value == 20.0


def test_dht22_requires_gpio():
    with pytest.raises(ValueError, match="gpio"):
        build_sensor("t", SensorSpec(kind="dht22_temp", metric="temperature"))


def test_fake_requires_value():
    with pytest.raises(ValueError, match="value"):
        build_sensor("f", SensorSpec(kind="fake", metric="temperature"))


def test_analog_cannot_be_auto_built():
    with pytest.raises(ValueError, match="analog"):
        build_sensor("a", SensorSpec(kind="analog", metric="co2_ppm", gpio=0))
