import asyncio
from datetime import datetime, timedelta, timezone

from pyfarm.control.alerts.channels.base import Notifier, RecordingChannel
from pyfarm.control.alerts.evaluator import AlertEvaluator
from pyfarm.control.engine.context import ControlContext, SensorReading
from pyfarm.control.spec.loader import load_spec


def _setup(oyster_spec_path, clock):
    spec = load_spec(oyster_spec_path)
    ctx = ControlContext.new(spec)
    push, telegram = RecordingChannel(), RecordingChannel()
    notifier = Notifier({"push": push, "telegram": telegram})
    evaluator = AlertEvaluator(notifier, clock=clock)
    return ctx, evaluator, push, telegram


def test_heat_alert_fires_and_routes_channels(oyster_spec_path):
    t0 = datetime(2026, 6, 15, tzinfo=timezone.utc)
    ctx, evaluator, push, telegram = _setup(oyster_spec_path, lambda: t0)
    ctx.record_reading("temperature", SensorReading(30.0, "celsius"))
    fired = asyncio.run(evaluator.evaluate(ctx))
    assert len(fired) == 1
    assert len(push.sent) == 1 and len(telegram.sent) == 1
    assert push.sent[0].severity == "critical"


def test_cooldown_suppresses_repeat(oyster_spec_path):
    now = {"t": datetime(2026, 6, 15, tzinfo=timezone.utc)}
    ctx, evaluator, push, _ = _setup(oyster_spec_path, lambda: now["t"])
    ctx.record_reading("temperature", SensorReading(30.0, "celsius"))
    asyncio.run(evaluator.evaluate(ctx))
    now["t"] += timedelta(minutes=5)  # within 30 min cooldown
    asyncio.run(evaluator.evaluate(ctx))
    assert len(push.sent) == 1
    now["t"] += timedelta(minutes=30)  # cooldown elapsed
    asyncio.run(evaluator.evaluate(ctx))
    assert len(push.sent) == 2


def test_missing_metric_does_not_crash(oyster_spec_path):
    # The co2 flatline alert references sensor.co2, which has no reading here.
    t0 = datetime(2026, 6, 15, tzinfo=timezone.utc)
    ctx, evaluator, push, _ = _setup(oyster_spec_path, lambda: t0)
    fired = asyncio.run(evaluator.evaluate(ctx))
    assert fired == []  # no crash, nothing fired
