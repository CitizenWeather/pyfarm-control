"""Tests for error handling and edge cases in the control engine."""

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from pyfarm.control.actuators.logging import LoggingActuator
from pyfarm.control.engine.context import ControlContext, SensorReading
from pyfarm.control.engine.errors import ReplayExhausted, SensorReadError
from pyfarm.control.engine.runner import ControlRunner
from pyfarm.control.sensors.base import Sensor
from pyfarm.control.sensors.replay import ReplaySensor
from pyfarm.control.spec.loader import load_spec


class _FailingSensor(Sensor):
    """Always raises SensorReadError."""

    async def read(self) -> SensorReading:
        raise SensorReadError("simulated hardware failure")


class _OneReadSensor(Sensor):
    """Returns one reading then raises SensorReadError."""

    def __init__(self, metric: str, value: float, unit: str = "") -> None:
        super().__init__(metric, unit)
        self._done = False
        self._value = value

    async def read(self) -> SensorReading:
        if self._done:
            raise SensorReadError("second read failure")
        self._done = True
        return SensorReading(value=self._value, unit=self.unit)


def _make_runner(oyster_spec_path, sensors, actuators=None):
    spec = load_spec(oyster_spec_path)
    if actuators is None:
        actuators = {name: LoggingActuator(name) for name in spec.actuators}
    return ControlRunner(spec, sensors, actuators)


# -- Sensor failure handling -------------------------------------------------

def test_sensor_failure_is_logged_not_raised(oyster_spec_path):
    """A SensorReadError should be logged as an event, not propagate to the caller."""
    runner = _make_runner(oyster_spec_path, [_FailingSensor("temperature", "celsius")])
    asyncio.run(runner.tick())
    failure_events = [e for e in runner.ctx.events if e.kind == "sensor_failure"]
    assert failure_events, "Expected a sensor_failure event"
    assert "temperature" in failure_events[0].data.get("metric", "")


def test_sensor_failure_holds_last_known_value(oyster_spec_path):
    """After a read failure, the last successful reading remains in context."""
    sensor = _OneReadSensor("temperature", 22.5, "celsius")
    runner = _make_runner(oyster_spec_path, [sensor])

    asyncio.run(runner.tick())  # first tick: read succeeds
    assert runner.ctx.readings["temperature"].value == 22.5

    asyncio.run(runner.tick())  # second tick: read fails
    assert runner.ctx.readings["temperature"].value == 22.5  # held


def test_replay_exhausted_propagates(oyster_spec_path):
    """ReplayExhausted must bubble up from tick() so run_until_exhausted can stop."""
    sensor = ReplaySensor("temperature", [20.0])
    runner = _make_runner(oyster_spec_path, [sensor])
    asyncio.run(runner.tick())  # consumes the one reading
    with pytest.raises(ReplayExhausted):
        asyncio.run(runner.tick())


def test_run_until_exhausted_stops_on_empty_sensor(oyster_spec_path):
    sensor = ReplaySensor("temperature", [20.0, 21.0, 22.0])
    runner = _make_runner(oyster_spec_path, [sensor])
    ticks = asyncio.run(runner.run_until_exhausted())
    assert ticks == 3


# -- Interlock error safety --------------------------------------------------

def test_bad_interlock_expression_fails_safe(oyster_spec_path):
    """If an interlock expression is unevaluatable, the actuator is forced off."""
    spec = load_spec(oyster_spec_path)
    misting = LoggingActuator("misting")
    # Patch the interlock to a syntactically broken expression at runtime.
    spec.actuators["misting"].interlock = "humidity_rh.current @@@ 0.95"
    runner = ControlRunner(spec, [], {"misting": misting})
    asyncio.run(runner.tick())
    # Misting should be off (fail-safe) because the interlock can't be evaluated.
    assert not runner.ctx.actuator_states["misting"].on


# -- Derived metrics edge cases ----------------------------------------------

def test_derived_metrics_skipped_when_readings_missing(oyster_spec_path):
    """If temperature or humidity is not yet known, derived metrics are not computed."""
    runner = _make_runner(oyster_spec_path, [])
    asyncio.run(runner.tick())
    assert "vpd" not in runner.ctx.derived
    assert "dew_point" not in runner.ctx.derived


def test_derived_metrics_computed_when_both_readings_present(oyster_spec_path):
    temp = ReplaySensor("temperature", [20.0], unit="celsius", loop=True)
    rh = ReplaySensor("humidity_rh", [0.8], loop=True)
    runner = _make_runner(oyster_spec_path, [temp, rh])
    asyncio.run(runner.tick())
    assert "vpd" in runner.ctx.derived
    assert runner.ctx.derived["vpd"] > 0


# -- Safety guard ------------------------------------------------------------

def test_safety_max_on_forces_actuator_off(oyster_spec_path):
    """An actuator exceeding its max_on_seconds limit is forced off."""
    spec = load_spec(oyster_spec_path)
    spec.actuators["misting"].safety.max_on_seconds = 1  # very short

    misting = LoggingActuator("misting")
    old_time = datetime.now(timezone.utc) - timedelta(seconds=10)
    runner = ControlRunner(spec, [], {"misting": misting})

    # Simulate that misting has been on for longer than max_on_seconds.
    runner.ctx.actuator_states["misting"].on = True
    runner.ctx.actuator_states["misting"].last_changed = old_time

    asyncio.run(runner.tick())
    assert not runner.ctx.actuator_states["misting"].on
