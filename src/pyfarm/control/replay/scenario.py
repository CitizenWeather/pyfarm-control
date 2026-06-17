"""Offline replay: run the full control engine over pre-recorded CSV sensor data.

This is the canonical entry point for deterministic testing and contributor
onboarding — no hardware required. Pair with any CSV that matches the spec's
expected metrics.
"""

from __future__ import annotations

from pathlib import Path

from pyfarm.control.actuators.logging import LoggingActuator
from pyfarm.control.engine.runner import ControlRunner
from pyfarm.control.sensors.replay import replay_sensors_from_csv
from pyfarm.control.spec.loader import load_spec


async def run_scenario(
    spec_path: str | Path,
    sensor_csv: str | Path,
    metrics: list[str] | None = None,
) -> ControlRunner:
    """Run the full control loop against pre-recorded sensor data.

    Loads the spec, builds :class:`LoggingActuator` instances for every
    actuator defined in the spec, drives the engine until sensor data is
    exhausted, then returns the runner so callers can inspect actuator logs
    and the event history.

    ``metrics`` filters which CSV columns are loaded as sensors. When
    ``None``, all non-timestamp columns are used.
    """
    spec = load_spec(spec_path)

    all_sensors = replay_sensors_from_csv(sensor_csv)
    sensors = (
        [s for s in all_sensors if s.metric in metrics]
        if metrics is not None
        else all_sensors
    )

    actuators = {name: LoggingActuator(name) for name in spec.actuators}

    runner = ControlRunner(spec, sensors, actuators, tick_seconds=0)
    await runner.run_until_exhausted()
    return runner
