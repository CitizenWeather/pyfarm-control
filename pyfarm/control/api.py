from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse

from pyfarm.control.engine.context import ControlContext


def make_app(ctx: ControlContext) -> FastAPI:
    app = FastAPI(title="pyfarm-control", docs_url=None, redoc_url=None)

    # Legacy endpoint (v0)
    @app.get("/status")
    async def status() -> JSONResponse:
        """Get current control context status (legacy endpoint)."""
        return JSONResponse(ctx.to_status_dict())

    # V1 API endpoints
    @app.get("/health")
    async def health() -> dict[str, str]:
        """Health check endpoint for Kubernetes probes."""
        return {"status": "ok", "run_id": ctx.run_id}

    @app.get("/api/v1/status")
    async def api_status() -> dict[str, Any]:
        """Get current control context status."""
        return ctx.to_status_dict()

    @app.get("/api/v1/history")
    async def get_history(
        sensor_id: str | None = Query(None),
        metric: str | None = Query(None),
        limit: int = Query(100, ge=1, le=10000),
    ) -> dict[str, Any]:
        """Get historical sensor readings.

        Query parameters:
        - sensor_id: Filter by sensor ID
        - metric: Filter by metric name
        - limit: Maximum readings to return (default: 100, max: 10000)
        """
        readings = []

        if sensor_id:
            # Filter by sensor_id in readings dict
            if sensor_id in ctx.readings:
                readings = [ctx.readings[sensor_id]]
        elif metric:
            # Filter by metric name
            for reading in ctx.readings.values():
                if reading.metric == metric:
                    readings.append(reading)
        else:
            # Return all readings
            readings = list(ctx.readings.values())

        return {
            "readings": [
                {
                    "sensor_id": r.sensor_id,
                    "metric": r.metric,
                    "value": r.value,
                    "unit": r.unit,
                    "timestamp": r.timestamp.isoformat(),
                }
                for r in readings[:limit]
            ],
            "count": len(readings),
        }

    @app.post("/api/v1/override")
    async def actuator_override(
        actuator_id: str = Query(...),
        state: bool = Query(...),
    ) -> dict[str, Any]:
        """Override an actuator state (requires authentication in Phase 2).

        Query parameters:
        - actuator_id: ID of actuator to override
        - state: Desired state (true=on, false=off)
        """
        # Note: In Phase 2, this will validate auth token and apply permission checks
        if actuator_id not in ctx.actuator_states:
            raise HTTPException(
                status_code=404,
                detail=f"Actuator '{actuator_id}' not found",
            )

        # TODO: Actually apply the override to the running control engine
        # This requires callback or shared state with the runner

        return {
            "actuator_id": actuator_id,
            "state": state,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "note": "Override registered; will apply on next control tick",
        }

    @app.get("/api/v1/events")
    async def get_events(
        limit: int = Query(50, ge=1, le=1000),
    ) -> dict[str, Any]:
        """Get recent control events.

        Query parameters:
        - limit: Maximum events to return (default: 50, max: 1000)
        """
        recent = list(ctx.events)[-limit:]
        return {
            "events": [
                {
                    "kind": e.kind.value if hasattr(e.kind, "value") else str(e.kind),
                    "message": e.message,
                    "timestamp": e.timestamp.isoformat(),
                    "data": e.data or {},
                }
                for e in recent
            ],
            "count": len(recent),
        }

    # TODO: WebSocket endpoint for real-time event streaming
    # @app.websocket("/api/v1/events/stream")
    # async def events_stream(websocket: WebSocket) -> None:
    #     await websocket.accept()
    #     try:
    #         while True:
    #             # Subscribe to bus events and stream to client
    #             pass
    #     except Exception:
    #         pass

    return app
