from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

from pyfarm.core.models import ControlEvent
from pyfarm.observability.event_bus import EventSink
from pyfarm.control.engine.context import ControlContext


class WebSocketEventManager(EventSink):
    """Broadcasts control events to all connected WebSocket clients."""

    def __init__(self):
        """Initialize with empty client set."""
        self.clients: set[WebSocket] = set()

    async def handle(self, event: ControlEvent) -> None:
        """Broadcast event to all connected clients."""
        message = {
            "kind": event.kind.value if hasattr(event.kind, "value") else str(event.kind),
            "message": event.message,
            "timestamp": event.timestamp.isoformat(),
            "data": event.data or {},
        }
        # Send to all connected clients, removing any that disconnect
        disconnected = set()
        for client in self.clients:
            try:
                await client.send_json(message)
            except Exception:
                # Client disconnected or errored; mark for removal
                disconnected.add(client)
        self.clients -= disconnected

    async def add_client(self, websocket: WebSocket) -> None:
        """Register a new WebSocket client."""
        await websocket.accept()
        self.clients.add(websocket)

    async def remove_client(self, websocket: WebSocket) -> None:
        """Unregister a WebSocket client."""
        self.clients.discard(websocket)
        try:
            await websocket.close()
        except Exception:
            pass


def make_app(ctx: ControlContext) -> FastAPI:
    app = FastAPI(title="pyfarm-control", docs_url=None, redoc_url=None)

    # WebSocket event manager for real-time streaming
    ws_manager = WebSocketEventManager()
    if ctx.bus is not None:
        ctx.bus.subscribe(ws_manager)

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
        duration_seconds: int = Query(86400),
    ) -> dict[str, Any]:
        """Override an actuator state (requires authentication in Phase 2).

        Query parameters:
        - actuator_id: ID of actuator to override
        - state: Desired state (true=on, false=off)
        - duration_seconds: How long override lasts (default: 86400 = 24h, max: 604800 = 1 week)
        """
        # Note: In Phase 2, this will validate auth token and apply permission checks
        if actuator_id not in ctx.actuator_states:
            raise HTTPException(
                status_code=404,
                detail=f"Actuator '{actuator_id}' not found",
            )

        # Validate duration
        duration_seconds = max(1, min(duration_seconds, 604800))  # 1 second to 1 week

        # Apply the override to the running control engine
        override = ctx.apply_actuator_override(actuator_id, state, duration_seconds)

        return {
            "actuator_id": actuator_id,
            "state": state,
            "applied_at": override.applied_at.isoformat(),
            "expires_at": override.expires_at.isoformat(),
            "note": "Override applied; will take effect on next control tick",
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

    @app.websocket("/api/v1/events/stream")
    async def events_stream(websocket: WebSocket) -> None:
        """WebSocket endpoint for real-time event streaming.

        Clients connect here and receive ControlEvents in real-time as they occur.
        """
        try:
            await ws_manager.add_client(websocket)
            # Keep connection open; events are sent via the event manager
            while True:
                # Keep the connection alive by waiting for messages (which we ignore)
                # The WebSocket will be kept open and events will be pushed via ws_manager
                _ = await websocket.receive_text()
        except WebSocketDisconnect:
            await ws_manager.remove_client(websocket)
        except Exception:
            await ws_manager.remove_client(websocket)

    return app
