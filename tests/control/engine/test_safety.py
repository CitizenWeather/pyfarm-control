from datetime import datetime, timedelta, timezone

from pyfarm.control.engine.context import ActuatorState
from pyfarm.control.engine.safety import SafetyGuard
from pyfarm.control.spec.schema import ActuatorSafety

T0 = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)


def test_min_off_time_blocks_short_cycle():
    guard = SafetyGuard(clock=lambda: T0)
    state = ActuatorState("misting", on=False, last_changed=T0 - timedelta(seconds=100))
    allowed, reason = guard.constrain(True, state, ActuatorSafety(min_off_seconds=300))
    assert allowed is False
    assert "min off-time" in reason


def test_min_off_time_allows_after_wait():
    guard = SafetyGuard(clock=lambda: T0)
    state = ActuatorState("misting", on=False, last_changed=T0 - timedelta(seconds=600))
    allowed, reason = guard.constrain(True, state, ActuatorSafety(min_off_seconds=300))
    assert allowed is True and reason is None


def test_max_on_time_forces_off():
    guard = SafetyGuard(clock=lambda: T0)
    state = ActuatorState("heater", on=True, last_changed=T0 - timedelta(minutes=61))
    allowed, reason = guard.constrain(True, state, ActuatorSafety(max_on_minutes=60))
    assert allowed is False
    assert "max on-time" in reason
