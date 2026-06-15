from datetime import datetime, timezone

from pyfarm.control.controllers.pid import PidController
from pyfarm.control.controllers.schedule import ScheduleController
from pyfarm.control.engine.context import ControlContext, SensorReading
from pyfarm.control.spec.loader import load_spec


def _at(hour, minute=0):
    return lambda: datetime(2026, 6, 15, hour, minute, tzinfo=timezone.utc)


def test_duty_cycle_on_window():
    # 5 minutes on each hour, aligned to midnight.
    ctrl = ScheduleController(on_seconds=300, period_seconds=3600, clock=_at(9, 2))
    assert ctrl.compute(None) is True  # 2 min past the hour, within 5 min
    ctrl_off = ScheduleController(on_seconds=300, period_seconds=3600, clock=_at(9, 30))
    assert ctrl_off.compute(None) is False


def test_light_photoperiod_from_stage(oyster_spec_path):
    spec = load_spec(oyster_spec_path)
    ctx = ControlContext.new(spec)
    ctx.current_stage_index = 1  # initiation: light "12/12"
    day = ScheduleController.for_light(clock=_at(6))
    night = ScheduleController.for_light(clock=_at(18))
    assert day.compute(ctx) is True   # before 12:00 -> lights on
    assert night.compute(ctx) is False


def test_pid_drives_toward_setpoint(oyster_spec_path):
    spec = load_spec(oyster_spec_path)
    ctx = ControlContext.new(spec)
    ctx.current_stage_index = 1  # temp target 18
    pid = PidController("temperature", "raise", kp=0.1)
    ctx.record_reading("temperature", SensorReading(value=10.0, unit="celsius"))
    cold = pid.compute(ctx)
    ctx.record_reading("temperature", SensorReading(value=17.0, unit="celsius"))
    warm = pid.compute(ctx)
    assert 0.0 <= warm <= 1.0
    assert cold > warm  # bigger error -> more output
