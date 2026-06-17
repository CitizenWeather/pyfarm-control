from __future__ import annotations

import asyncio
from pathlib import Path

from pyfarm.core.models import Unit
from pyfarm.control.spec.loader import load_spec
from pyfarm.control.extensions import build_actuator
from pyfarm.control.engine.runner import ControlRunner
from .fake_sensor import ReplaySensor

_METRIC_UNITS = {
    "temperature": Unit.CELSIUS,
    "humidity_rh": Unit.PERCENT,
    "co2_ppm": Unit.PPM,
}


async def run_scenario(
    spec_path: str | Path,
    sensor_csv: str | Path,
    metrics: list[str] | None = None,
) -> ControlRunner:
    """
    Run the full control loop against pre-recorded sensor data.

    metrics defaults to [temperature, humidity_rh, co2_ppm].
    The CSV must have a 'timestamp' column plus one column per metric.
    """
    spec = load_spec(spec_path)
    metrics = metrics or list(_METRIC_UNITS.keys())

    sensors = [
        ReplaySensor(sensor_csv, metric=m, unit=_METRIC_UNITS.get(m, Unit.UNITLESS))
        for m in metrics
    ]
    actuators = {
        name: build_actuator(name, actuator_spec)
        for name, actuator_spec in spec.actuators.items()
    }
    runner = ControlRunner(spec=spec, sensors=sensors, actuators=actuators, tick_seconds=0)

    # Drive ticks until all sensor streams are exhausted
    while not all(s.exhausted for s in sensors):
        await runner._tick()
        await asyncio.sleep(0)

    return runner
