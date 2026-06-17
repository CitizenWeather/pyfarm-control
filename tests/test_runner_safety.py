import asyncio
from datetime import datetime, timedelta, timezone

from pyfarm.core.models import ActuatorState
from pyfarm.control.extensions import build_actuator
from pyfarm.control.engine.runner import ControlRunner
from pyfarm.control.spec.schema import GrowSpec


def _spec_with_unsafe_actuator() -> GrowSpec:
    return GrowSpec(
        spec_version="1.0",
        kind="GrowSpec",
        metadata={"name": "safety-test"},
        stages=[
            {
                "name": "s",
                "duration": {"min_days": 1, "max_days": 2},
                "exit_condition": {"metric": "temperature", "threshold": ">= 99"},
                "setpoints": {},
            }
        ],
        actuators={"fan": {"kind": "relay", "gpio": 1}},  # note: no `safety:` block
    )


def test_tick_does_not_crash_when_safety_is_none():
    """Regression: actuator_spec.safety defaults to None; the safety block must
    not dereference it. Previously raised AttributeError on the second tick."""
    spec = _spec_with_unsafe_actuator()
    actuators = {"fan": build_actuator("fan", spec.actuators["fan"])}
    runner = ControlRunner(spec=spec, sensors=[], actuators=actuators, tick_seconds=0)

    # Seed a prior state with last_toggled_at set so the safety branch is entered.
    runner.ctx.actuator_states["fan"] = ActuatorState(
        name="fan",
        state=True,
        last_toggled_at=datetime.now(timezone.utc) - timedelta(seconds=5),
    )

    asyncio.run(runner._tick())  # must not raise

    # The actuator was still commanded (safety simply didn't apply).
    assert "fan" in runner.ctx.actuator_states
