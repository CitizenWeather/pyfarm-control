"""SQLite-backed store for full run history.

Implements :class:`pyfarm.control.engine.store.SnapshotStore` so it can be
passed directly to :class:`ControlRunner` as its ``store=`` argument.  Each
``write_snapshot`` call also appends any new events from ``ctx.events`` and
the latest sensor readings, building an append-only audit trail for the run.

Query helpers on the store are used by the history API and the CLI export
commands.
"""

from __future__ import annotations

import json
import sqlite3
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pyfarm.control.engine.context import ControlContext, ControlEvent, SensorReading
from pyfarm.control.engine.store import SnapshotStore


class SQLiteStore(SnapshotStore):
    """Full run history in SQLite plus crash-recovery via the SnapshotStore API.

    The store is safe to construct before a run starts — the schema is created
    lazily on first access.  Each run is identified by ``ctx.run_id`` which is
    set by :meth:`ControlContext.new`.
    """

    def __init__(self, db_path: str | Path = "pyfarm.db") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        # Track how many events we have already flushed so write_snapshot only
        # inserts genuinely new ones.
        self._flushed_event_count: dict[str, int] = {}
        self._init_schema()

    # ------------------------------------------------------------------
    # SnapshotStore interface (crash recovery)
    # ------------------------------------------------------------------

    async def write_snapshot(self, ctx: ControlContext) -> None:
        """Persist current readings, actuator states, and any new events."""
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            self._ensure_run(conn, ctx)
            self._flush_readings(conn, ctx, now)
            self._flush_actuator_states(conn, ctx, now)
            self._flush_events(conn, ctx)
            conn.commit()

    def restore(self, ctx: ControlContext) -> bool:
        """Rehydrate stage position and last readings from a prior run snapshot.

        Returns ``True`` if a snapshot was found for ``ctx.run_id``.
        """
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT current_stage_index, stage_entered_at FROM runs WHERE run_id = ?",
                (ctx.run_id,),
            ).fetchone()
            if row is None:
                return False
            ctx.current_stage_index = row[0]
            ctx.stage_entered_at = datetime.fromisoformat(row[1])

            for metric, value, unit, ts in conn.execute(
                """SELECT metric, value, unit, timestamp
                   FROM sensor_readings
                   WHERE run_id = ?
                   ORDER BY timestamp DESC""",
                (ctx.run_id,),
            ).fetchall():
                if metric not in ctx.readings:
                    ctx.record_reading(
                        metric,
                        SensorReading(
                            value=value,
                            unit=unit,
                            timestamp=datetime.fromisoformat(ts),
                        ),
                    )
        return True

    # ------------------------------------------------------------------
    # History query API (used by FastAPI routes and CLI export)
    # ------------------------------------------------------------------

    def new_run(self, run_id: str, spec_name: str) -> None:
        """Explicitly register a new run — called by the CLI before runner.run()."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR IGNORE INTO runs (run_id, spec_name, started_at, current_stage_index, stage_entered_at) "
                "VALUES (?, ?, ?, 0, ?)",
                (run_id, spec_name, datetime.now(timezone.utc).isoformat(),
                 datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()

    def end_run(self, run_id: str, final_stage: str | None = None) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE runs SET ended_at = ?, final_stage = ? WHERE run_id = ?",
                (datetime.now(timezone.utc).isoformat(), final_stage, run_id),
            )
            conn.commit()

    def list_runs(self, limit: int = 100) -> list[dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT run_id, spec_name, started_at, ended_at, final_stage "
                "FROM runs ORDER BY started_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            dict(run_id=r[0], spec_name=r[1], started_at=r[2], ended_at=r[3], final_stage=r[4])
            for r in rows
        ]

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT run_id, spec_name, started_at, ended_at, final_stage "
                "FROM runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
        if row is None:
            return None
        return dict(run_id=row[0], spec_name=row[1], started_at=row[2], ended_at=row[3], final_stage=row[4])

    def get_sensor_readings(
        self,
        run_id: str,
        metric: str | None = None,
        start: str | None = None,
        end: str | None = None,
    ) -> list[dict[str, Any]]:
        query = "SELECT metric, value, unit, timestamp FROM sensor_readings WHERE run_id = ?"
        params: list[Any] = [run_id]
        if metric:
            query += " AND metric = ?"
            params.append(metric)
        if start:
            query += " AND timestamp >= ?"
            params.append(start)
        if end:
            query += " AND timestamp <= ?"
            params.append(end)
        query += " ORDER BY timestamp"
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(query, params).fetchall()
        return [dict(metric=r[0], value=r[1], unit=r[2], timestamp=r[3]) for r in rows]

    def get_events(
        self,
        run_id: str,
        kind: str | None = None,
    ) -> list[dict[str, Any]]:
        query = "SELECT kind, message, data, timestamp FROM events WHERE run_id = ?"
        params: list[Any] = [run_id]
        if kind:
            query += " AND kind = ?"
            params.append(kind)
        query += " ORDER BY timestamp"
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(query, params).fetchall()
        return [
            dict(kind=r[0], message=r[1], data=json.loads(r[2]) if r[2] else {}, timestamp=r[3])
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _init_schema(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS runs (
                    run_id              TEXT PRIMARY KEY,
                    spec_name           TEXT NOT NULL,
                    started_at          TEXT NOT NULL,
                    ended_at            TEXT,
                    final_stage         TEXT,
                    current_stage_index INTEGER NOT NULL DEFAULT 0,
                    stage_entered_at    TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sensor_readings (
                    id        INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id    TEXT NOT NULL,
                    metric    TEXT NOT NULL,
                    value     REAL NOT NULL,
                    unit      TEXT NOT NULL,
                    timestamp TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_readings_run_metric
                    ON sensor_readings(run_id, metric);
                CREATE TABLE IF NOT EXISTS events (
                    id        INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id    TEXT NOT NULL,
                    kind      TEXT NOT NULL,
                    message   TEXT NOT NULL,
                    data      TEXT,
                    timestamp TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_events_run_kind
                    ON events(run_id, kind);
                CREATE TABLE IF NOT EXISTS actuator_states (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id       TEXT NOT NULL,
                    name         TEXT NOT NULL,
                    on_state     INTEGER NOT NULL,
                    last_changed TEXT NOT NULL,
                    timestamp    TEXT NOT NULL
                );
            """)

    def _ensure_run(self, conn: sqlite3.Connection, ctx: ControlContext) -> None:
        conn.execute(
            "INSERT OR IGNORE INTO runs "
            "(run_id, spec_name, started_at, current_stage_index, stage_entered_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                ctx.run_id,
                ctx.spec.metadata.name,
                datetime.now(timezone.utc).isoformat(),
                ctx.current_stage_index,
                ctx.stage_entered_at.isoformat(),
            ),
        )
        # Keep stage index current on every snapshot.
        conn.execute(
            "UPDATE runs SET current_stage_index = ?, stage_entered_at = ? WHERE run_id = ?",
            (ctx.current_stage_index, ctx.stage_entered_at.isoformat(), ctx.run_id),
        )

    def _flush_readings(
        self, conn: sqlite3.Connection, ctx: ControlContext, now: str
    ) -> None:
        for metric, reading in ctx.readings.items():
            conn.execute(
                "INSERT INTO sensor_readings (run_id, metric, value, unit, timestamp) "
                "VALUES (?, ?, ?, ?, ?)",
                (ctx.run_id, metric, reading.value, reading.unit, reading.timestamp.isoformat()),
            )

    def _flush_actuator_states(
        self, conn: sqlite3.Connection, ctx: ControlContext, now: str
    ) -> None:
        for name, state in ctx.actuator_states.items():
            conn.execute(
                "INSERT INTO actuator_states (run_id, name, on_state, last_changed, timestamp) "
                "VALUES (?, ?, ?, ?, ?)",
                (ctx.run_id, name, int(state.on), state.last_changed.isoformat(), now),
            )

    def _flush_events(self, conn: sqlite3.Connection, ctx: ControlContext) -> None:
        events = list(ctx.events)
        already_flushed = self._flushed_event_count.get(ctx.run_id, 0)
        new_events = events[already_flushed:]
        for event in new_events:
            conn.execute(
                "INSERT INTO events (run_id, kind, message, data, timestamp) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    ctx.run_id,
                    event.kind,
                    event.message,
                    json.dumps(event.data) if event.data else None,
                    event.timestamp.isoformat(),
                ),
            )
        self._flushed_event_count[ctx.run_id] = len(events)
