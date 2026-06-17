"""Minimal FastAPI status endpoint for a running ControlRunner."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from pyfarm.control.engine.context import ControlContext


def _elapsed_days(ctx: ControlContext) -> float:
    return (datetime.now(timezone.utc) - ctx.stage_entered_at).total_seconds() / 86400.0


def _is_stale(ts: datetime, threshold_seconds: float = 60.0) -> bool:
    ts_aware = ts if ts.tzinfo is not None else ts.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - ts_aware).total_seconds() > threshold_seconds


def make_app(ctx: ControlContext) -> FastAPI:
    """Return a FastAPI app that exposes a ``/status`` endpoint backed by ``ctx``."""
    app = FastAPI(title="pyfarm-control", docs_url=None, redoc_url=None)

    @app.get("/status")
    async def status() -> JSONResponse:
        return JSONResponse(_build_status(ctx))

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
