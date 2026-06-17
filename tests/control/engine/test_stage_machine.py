import asyncio
from datetime import datetime, timedelta, timezone

from pyfarm.control.engine.context import ControlContext
from pyfarm.control.engine.stage_machine import StageMachine
from pyfarm.control.spec.loader import load_spec


def test_advances_when_exit_condition_met(oyster_spec_path):
    spec = load_spec(oyster_spec_path)
    ctx = ControlContext.new(spec)
    sm = StageMachine()
    ctx.manual["visual.colonisation_pct"] = 0.97  # >= 0.95
    advanced = asyncio.run(sm.evaluate(ctx))
    assert advanced is True
    assert ctx.current_stage.name == "initiation"


def test_does_not_advance_when_unmet(oyster_spec_path):
    spec = load_spec(oyster_spec_path)
    ctx = ControlContext.new(spec)
    sm = StageMachine()
    ctx.manual["visual.colonisation_pct"] = 0.50
    assert asyncio.run(sm.evaluate(ctx)) is False
    assert ctx.current_stage.name == "colonisation"


def test_enum_threshold(oyster_spec_path):
    spec = load_spec(oyster_spec_path)
    ctx = ControlContext.new(spec)
    ctx.current_stage_index = 2  # fruiting, enum exit "starting_to_flatten"
    sm = StageMachine()
    ctx.manual["visual.cap_margin"] = "growing"
    assert asyncio.run(sm.evaluate(ctx)) is False  # final stage anyway, not met


def test_overdue_event_logged(oyster_spec_path):
    spec = load_spec(oyster_spec_path)
    clock = lambda: datetime(2026, 6, 15, tzinfo=timezone.utc)
    ctx = ControlContext.new(spec)
    ctx.stage_entered_at = clock() - timedelta(days=40)  # past colonisation max 28
    sm = StageMachine(clock=clock, day_seconds=86400)
    asyncio.run(sm.evaluate(ctx))
    assert any(e.kind == "stage_overdue" for e in ctx.events)
