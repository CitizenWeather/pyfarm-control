"""Persistence of the live context for crash recovery.

The default store is a no-op; :class:`JsonSnapshotStore` writes a small JSON
snapshot of the volatile state (stage index, when it was entered, last
readings) that :meth:`restore` can rehydrate onto a fresh context.
"""

from __future__ import annotations

import abc
import json
from datetime import datetime
from pathlib import Path

from pyfarm.control.engine.context import ControlContext, SensorReading


class SnapshotStore(abc.ABC):
    @abc.abstractmethod
    async def write_snapshot(self, ctx: ControlContext) -> None: ...

    @abc.abstractmethod
    def restore(self, ctx: ControlContext) -> bool:
        """Rehydrate ``ctx`` in place from the last snapshot. Returns True if a
        snapshot was found and applied."""


class NullStore(SnapshotStore):
    async def write_snapshot(self, ctx: ControlContext) -> None:
        return None

    def restore(self, ctx: ControlContext) -> bool:
        return False


class JsonSnapshotStore(SnapshotStore):
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    async def write_snapshot(self, ctx: ControlContext) -> None:
        data = {
            "run_id": ctx.run_id,
            "current_stage_index": ctx.current_stage_index,
            "stage_entered_at": ctx.stage_entered_at.isoformat(),
            "readings": {
                metric: {
                    "value": r.value,
                    "unit": r.unit,
                    "timestamp": r.timestamp.isoformat(),
                }
                for metric, r in ctx.readings.items()
            },
            "derived": dict(ctx.derived),
            "manual": dict(ctx.manual),
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, indent=2))

    def restore(self, ctx: ControlContext) -> bool:
        if not self.path.exists():
            return False
        data = json.loads(self.path.read_text())
        ctx.run_id = data.get("run_id", ctx.run_id)
        ctx.current_stage_index = data.get("current_stage_index", 0)
        ctx.stage_entered_at = datetime.fromisoformat(data["stage_entered_at"])
        ctx.derived = dict(data.get("derived", {}))
        ctx.manual = dict(data.get("manual", {}))
        for metric, r in data.get("readings", {}).items():
            ctx.record_reading(
                metric,
                SensorReading(
                    value=r["value"],
                    unit=r["unit"],
                    timestamp=datetime.fromisoformat(r["timestamp"]),
                ),
            )
        return True
