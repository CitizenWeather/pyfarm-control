from datetime import datetime, timezone

from pyfarm.control.controllers.hysteresis import HysteresisController
from pyfarm.control.engine.context import ControlContext, SensorReading
from pyfarm.control.spec.loader import load_spec


def _ctx(oyster_spec_path, stage_index=1):
    spec = load_spec(oyster_spec_path)
    ctx = ControlContext.new(spec)
    ctx.current_stage_index = stage_index  # initiation: temp target 18 ±2
    return ctx


def _set(ctx, metric, value):
    ctx.record_reading(metric, SensorReading(value=value, unit=""))


def test_heater_turns_on_below_deadband(oyster_spec_path):
    ctx = _ctx(oyster_spec_path)
    ctrl = HysteresisController("temperature", "raise")
    _set(ctx, "temperature", 15.0)  # < 18 - 2
    assert ctrl.compute(ctx) is True


def test_heater_holds_in_deadband(oyster_spec_path):
    ctx = _ctx(oyster_spec_path)
    ctrl = HysteresisController("temperature", "raise")
    _set(ctx, "temperature", 15.0)
    ctrl.compute(ctx)  # ON
    _set(ctx, "temperature", 17.5)  # inside deadband, not yet at target
    assert ctrl.compute(ctx) is True  # holds ON until it reaches target


def test_heater_turns_off_at_target(oyster_spec_path):
    ctx = _ctx(oyster_spec_path)
    ctrl = HysteresisController("temperature", "raise")
    _set(ctx, "temperature", 15.0)
    ctrl.compute(ctx)
    _set(ctx, "temperature", 18.0)
    assert ctrl.compute(ctx) is False


def test_lower_direction_for_cooling(oyster_spec_path):
    ctx = _ctx(oyster_spec_path)
    ctrl = HysteresisController("co2_ppm", "lower")  # target 800 ±200
    _set(ctx, "co2_ppm", 1200.0)  # > 800 + 200
    assert ctrl.compute(ctx) is True
    _set(ctx, "co2_ppm", 800.0)
    assert ctrl.compute(ctx) is False


def test_off_when_no_reading(oyster_spec_path):
    ctx = _ctx(oyster_spec_path)
    ctrl = HysteresisController("temperature", "raise")
    assert ctrl.compute(ctx) is False
