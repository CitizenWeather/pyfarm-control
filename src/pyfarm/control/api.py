"""FastAPI status and history endpoints for a running ControlRunner."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse

from pyfarm.control.engine.context import ControlContext

if TYPE_CHECKING:
    from pyfarm.control.persist.sqlite import SQLiteStore


def _elapsed_days(ctx: ControlContext) -> float:
    return (datetime.now(timezone.utc) - ctx.stage_entered_at).total_seconds() / 86400.0


def _is_stale(ts: datetime, threshold_seconds: float = 60.0) -> bool:
    ts_aware = ts if ts.tzinfo is not None else ts.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - ts_aware).total_seconds() > threshold_seconds


def make_app(ctx: ControlContext, store: SQLiteStore | None = None) -> FastAPI:
    """Return a FastAPI app backed by ``ctx``.

    Pass an optional ``store`` to also expose ``/history/*`` and ``/runs``
    endpoints for querying past runs and sensor data.
    """
    app = FastAPI(title="pyfarm-control", docs_url=None, redoc_url=None)

    @app.get("/status")
    async def status() -> JSONResponse:
        return JSONResponse(_build_status(ctx))

    if store is not None:
        @app.get("/runs")
        async def list_runs(limit: int = Query(100, ge=1, le=1000)) -> JSONResponse:
            """List recent runs with metadata."""
            return JSONResponse({"runs": store.list_runs(limit)})

        @app.get("/history/sensor-readings")
        async def get_sensor_readings(
            run_id: str | None = None,
            metric: str | None = None,
            start: str | None = None,
            end: str | None = None,
        ) -> JSONResponse:
            """Historical sensor readings, optionally filtered by metric or time range."""
            rid = run_id or ctx.run_id
            readings = store.get_sensor_readings(rid, metric=metric, start=start, end=end)
            return JSONResponse({"run_id": rid, "readings": readings})

        @app.get("/history/events")
        async def get_events(
            run_id: str | None = None,
            kind: str | None = None,
        ) -> JSONResponse:
            """Historical control events, optionally filtered by kind."""
            rid = run_id or ctx.run_id
            events = store.get_events(rid, kind=kind)
            return JSONResponse({"run_id": rid, "events": events})

    return app


def _build_status(ctx: ControlContext) -> dict[str, Any]:
    readings: dict[str, Any] = {}
    for metric, reading in ctx.readings.items():
        readings[metric] = {
            "value": reading.value,
            "unit": reading.unit,
            "stale": _is_stale(reading.timestamp),
        }

    recent_events = [
        {"kind": e.kind, "message": e.message, "timestamp": e.timestamp.isoformat()}
        for e in list(ctx.events)[-20:]
    ]

    return {
        "run_id": ctx.run_id,
        "spec_name": ctx.spec.metadata.name,
        "current_stage": ctx.current_stage.name,
        "elapsed_days": round(_elapsed_days(ctx), 4),
        "readings": readings,
        "derived": dict(ctx.derived),
        "recent_events": recent_events,
    }

