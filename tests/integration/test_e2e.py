"""End-to-end integration test: grow spec → runner tick → storage → analytics.

Uses the bundled oyster fruiting example spec and replay CSV — no hardware,
no network, no external services.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from pyfarm.control.engine.runner import ControlRunner
from pyfarm.control.replay.fake_sensor import ReplaySensor
from pyfarm.control.spec.loader import load_spec
from pyfarm.core.models import SensorReading
from pyfarm.core.storage_impl import SQLiteBackend

EXAMPLES = Path(__file__).parent.parent.parent / "examples"
SPEC_PATH = EXAMPLES / "oyster_fruiting.pyfarm.yaml"
CSV_PATH = EXAMPLES / "sample_sensor_data.csv"


@pytest.fixture
async def storage():
    """In-memory SQLite backend, connected and cleaned up per test."""
    backend = SQLiteBackend(":memory:")
    await backend.connect()
    yield backend
    await backend.close()


@pytest.fixture
def grow_spec(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "test-chat")
    return load_spec(SPEC_PATH)


@pytest.mark.asyncio
async def test_runner_tick_stores_readings(grow_spec, storage):
    """A single runner tick should persist sensor readings to storage."""
    sensor_temp = ReplaySensor(CSV_PATH, "temperature")
    sensor_rh = ReplaySensor(CSV_PATH, "humidity_rh")

    runner = ControlRunner(
        spec=grow_spec,
        sensors=[sensor_temp, sensor_rh],
        actuators={},
        store=storage,
    )

    await runner._tick()

    # Readings are stored by sensor_id (empty string for replay sensor).
    # CSV replay timestamps are historic (2024), so use a wide window.
    rows = await storage.get_readings(
        "",
        datetime(2020, 1, 1, tzinfo=timezone.utc),
        datetime(2030, 1, 1, tzinfo=timezone.utc),
    )
    assert len(rows) >= 2, f"Expected ≥2 readings in storage, got {len(rows)}"
    metrics = {r["metric"] for r in rows}
    assert "temperature" in metrics
    assert "humidity_rh" in metrics


@pytest.mark.asyncio
async def test_runner_tick_updates_context(grow_spec, storage):
    """After one tick the runner context should hold the sensor values."""
    sensor_temp = ReplaySensor(CSV_PATH, "temperature")

    runner = ControlRunner(
        spec=grow_spec,
        sensors=[sensor_temp],
        actuators={},
        store=storage,
    )

    await runner._tick()

    assert "temperature" in runner.ctx.readings
    reading = runner.ctx.readings["temperature"]
    assert reading.value > 0


@pytest.mark.asyncio
async def test_analytics_environment_summary(storage):
    """Analytics Analyzer should compute a non-zero summary from stored readings."""
    from pyfarm.analytics.analyzer import Analyzer

    now = datetime.now(timezone.utc)
    start = now - timedelta(hours=1)
    end = now + timedelta(hours=1)

    # Insert env-sensor readings that match what EnvironmentAnalyzer looks for.
    for i, (temp, rh) in enumerate([(18.2, 0.93), (18.0, 0.94), (17.9, 0.95)]):
        ts = now - timedelta(minutes=10 * i)
        await storage.insert_sensor_reading(
            SensorReading(timestamp=ts, metric="temperature", value=temp, unit="celsius", sensor_id="env")
        )
        await storage.insert_sensor_reading(
            SensorReading(timestamp=ts, metric="humidity", value=rh, unit="rh", sensor_id="env")
        )

    analyzer = Analyzer(storage)
    summary = await analyzer.environment_summary("test-grow", start, end)

    assert summary.mean_temp > 0, "Expected non-zero mean temperature"
    assert summary.mean_rh > 0, "Expected non-zero mean RH"


@pytest.mark.asyncio
async def test_full_pipeline(grow_spec, storage):
    """Full pipeline: load spec → tick → check storage → run analytics."""
    from pyfarm.analytics.analyzer import Analyzer

    sensor_temp = ReplaySensor(CSV_PATH, "temperature")
    sensor_rh = ReplaySensor(CSV_PATH, "humidity_rh")

    runner = ControlRunner(
        spec=grow_spec,
        sensors=[sensor_temp, sensor_rh],
        actuators={},
        store=storage,
    )

    # Tick 3 times to accumulate readings
    for _ in range(3):
        await runner._tick()

    # Confirm the context advanced (VPD derived if both sensors present)
    assert "vpd" in runner.ctx.derived, "VPD should be computed when temp+RH available"

    # Confirm snapshot was written
    # write_snapshot uses getattr(ctx, "grow_id", "default"); ControlContext
    # exposes run_id not grow_id, so snapshots land under "default".
    snapshot = await storage.get_latest_snapshot("default")
    assert snapshot is not None, "Expected snapshot after tick"
    assert "run_id" in snapshot

    # Confirm stage is still colonisation (we only ran 3 ticks, far from exit condition)
    assert runner.ctx.current_stage.name == "colonisation"

    # Analytics: re-label runner readings (stored with sensor_id="") as "env"
    # so EnvironmentAnalyzer can find them.  CSV timestamps are 2024 so use
    # a wide window spanning both the source data and the insert time.
    wide_start = datetime(2020, 1, 1, tzinfo=timezone.utc)
    wide_end = datetime(2030, 1, 1, tzinfo=timezone.utc)
    for r in await storage.get_readings("", wide_start, wide_end):
        ts = r["timestamp"]
        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts)
        await storage.insert_sensor_reading(
            SensorReading(
                timestamp=ts,
                metric=r["metric"],
                value=r["value"],
                unit=r["unit"] or "",
                sensor_id="env",
            )
        )

    analyzer = Analyzer(storage)
    summary = await analyzer.environment_summary(
        runner.ctx.run_id,
        wide_start,
        wide_end,
    )
    assert summary.mean_temp > 0
