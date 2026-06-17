import asyncio
from datetime import datetime, timezone

from pyfarm.core.models import ControlEvent, EventKind, SensorReading, Unit
from pyfarm.control.engine.runner import ControlRunner
from pyfarm.control.extensions.sinks import NotifierSink
from pyfarm.control.spec.schema import GrowSpec


class FakeNotifier:
    def __init__(self, name):
        self.name = name
        self.received: list[ControlEvent] = []

    async def send(self, event: ControlEvent) -> None:
        self.received.append(event)


def _spec_with_alert() -> GrowSpec:
    return GrowSpec(
        spec_version="1.0",
        kind="GrowSpec",
        metadata={"name": "alert-test"},
        stages=[
            {
                "name": "s",
                "duration": {"min_days": 1, "max_days": 2},
                "exit_condition": {"metric": "temperature", "threshold": ">= 99"},
                "setpoints": {},
            }
        ],
        alerts=[
            {
                "condition": "temperature.current > 28",
                "severity": "critical",
                "message": "Heat stress",
                "channels": ["ops"],
            }
        ],
    )


def test_alert_reaches_notifier_through_the_bus():
    """End-to-end: a firing alert flows ctx.log -> bus -> drain -> NotifierSink -> notifier."""
    spec = _spec_with_alert()
    ops = FakeNotifier("ops")
    sink = NotifierSink({"ops": ops})
    runner = ControlRunner(
        spec=spec, sensors=[], actuators={}, notifier=sink, tick_seconds=0
    )

    # Seed a reading that trips the alert condition (temperature.current > 28).
    runner.ctx.readings["temperature"] = SensorReading(
        value=30.0, unit=Unit.CELSIUS, timestamp=datetime.now(timezone.utc), metric="temperature"
    )

    asyncio.run(runner._tick())

    assert [e.message for e in ops.received] == ["Heat stress"]
    assert ops.received[0].kind == EventKind.ALERT_FIRED
