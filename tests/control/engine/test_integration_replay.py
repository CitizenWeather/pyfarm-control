"""End-to-end: load the reference spec, drive the full engine over a recorded
scenario with ReplaySensors and LoggingActuators, and inspect what it would
have done. No hardware, fully deterministic."""

import asyncio

from pyfarm.control.actuators.logging import LoggingActuator
from pyfarm.control.alerts.channels.base import Notifier, RecordingChannel
from pyfarm.control.alerts.evaluator import AlertEvaluator
from pyfarm.control.controllers.hysteresis import HysteresisController
from pyfarm.control.engine.context import ControlContext
from pyfarm.control.engine.runner import ControlRunner
from pyfarm.control.sensors.replay import ReplaySensor
from pyfarm.control.spec.loader import load_spec


def test_full_replay_run(oyster_spec_path):
    spec = load_spec(oyster_spec_path)

    # A recorded scenario: dry air (misting wanted), a heat spike, steady CO2.
    temps = [16.0, 30.0, 17.0, 17.5, 18.0]   # sample 2 is a heat-stress spike
    rh = [0.85, 0.86, 0.84, 0.83, 0.88]      # consistently below the 0.95 target
    co2 = [900.0, 850.0, 820.0, 810.0, 800.0]
    sensors = [
        ReplaySensor("temperature", temps, "celsius"),
        ReplaySensor("humidity_rh", rh),
        ReplaySensor("co2_ppm", co2, "ppm"),
    ]

    misting = LoggingActuator("misting")
    heater = LoggingActuator("heater")
    exhaust = LoggingActuator("exhaust_fan")
    actuators = {"misting": misting, "heater": heater, "exhaust_fan": exhaust}

    controllers = {
        "misting": HysteresisController("humidity_rh", "raise"),
        "heater": HysteresisController("temperature", "raise"),
        "exhaust_fan": HysteresisController("co2_ppm", "lower"),
    }

    push, telegram = RecordingChannel(), RecordingChannel()
    notifier = Notifier({"push": push, "telegram": telegram})
    alert_evaluator = AlertEvaluator(notifier)

    ctx = ControlContext.new(spec)
    # Vision/manual observations that drive stage progression.
    ctx.manual["visual.colonisation_pct"] = 0.97  # colonisation -> initiation
    ctx.manual["visual.pins_count"] = 12          # initiation  -> fruiting
    ctx.manual["visual.cap_margin"] = "growing"   # fruiting stays (final)

    runner = ControlRunner(
        spec,
        sensors,
        actuators,
        controllers=controllers,
        alert_evaluator=alert_evaluator,
        context=ctx,
    )

    ticks = asyncio.run(runner.run_until_exhausted())

    assert ticks == len(temps)
    # Progressed all the way to the final stage.
    assert ctx.current_stage.name == "fruiting"
    # Misting was disabled during colonisation but fired once enabled, since
    # humidity sat below the interlock threshold (0.95) and the setpoint.
    assert any(LoggingActuator.is_on(c.command) for c in misting.transitions)
    # The heat-stress spike (30C) raised a critical alert to both channels.
    assert any(n.severity == "critical" for n in push.sent)
    assert len(telegram.sent) >= 1
    # The engine recorded a stage transition event.
    assert any(e.kind == "stage_advanced" for e in ctx.events)
