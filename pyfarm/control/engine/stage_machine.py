from __future__ import annotations

import re
from datetime import datetime
from typing import Callable

from pyfarm.core.models import EventKind
from pyfarm.control.spec.schema import Stage
from .context import ControlContext

_THRESHOLD_RE = re.compile(r"^(>=|<=|>|<|==)\s*([0-9.]+)$")
_OPS: dict[str, Callable[[float, float], bool]] = {
    ">=": lambda a, b: a >= b,
    "<=": lambda a, b: a <= b,
    ">": lambda a, b: a > b,
    "<": lambda a, b: a < b,
    "==": lambda a, b: a == b,
}


class StageMachine:
    async def evaluate(self, ctx: ControlContext) -> bool:
        """Check exit conditions and advance the stage if met. Returns True if advanced."""
        stage = ctx.current_stage
        elapsed_days = (
            (datetime.utcnow() - ctx.stage_entered_at).total_seconds() / 86400
        )

        if elapsed_days < stage.duration.min_days:
            return False

        if elapsed_days > stage.duration.max_days:
            ctx.log(
                EventKind.SYSTEM,
                f"Stage '{stage.name}' exceeded max_days={stage.duration.max_days} — advancing",
            )
            return self._advance(ctx)

        if self._exit_condition_met(stage, ctx):
            ctx.log(
                EventKind.STAGE_TRANSITION,
                f"Exit condition met for stage '{stage.name}': "
                f"{stage.exit_condition.metric} {stage.exit_condition.threshold}",
            )
            return self._advance(ctx)

        return False

    def _exit_condition_met(self, stage: Stage, ctx: ControlContext) -> bool:
        cond = stage.exit_condition
        value = self._resolve_metric(cond.metric, ctx)
        if value is None:
            return False
        m = _THRESHOLD_RE.match(cond.threshold.strip())
        if m:
            op_str, rhs = m.group(1), float(m.group(2))
            return _OPS[op_str](float(value), rhs)
        # Enum / string threshold
        return str(value) == cond.threshold.strip()

    def _resolve_metric(self, metric: str, ctx: ControlContext):
        parts = metric.split(".")
        if parts[0] == "visual":
            return ctx.derived.get(metric)
        reading = ctx.readings.get(parts[0])
        if reading is not None:
            return reading.value
        return ctx.derived.get(metric)

    def _advance(self, ctx: ControlContext) -> bool:
        next_idx = ctx.current_stage_index + 1
        if next_idx >= len(ctx.spec.stages):
            ctx.log(EventKind.SYSTEM, "All stages complete — grow finished")
            return False
        ctx.current_stage_index = next_idx
        ctx.stage_entered_at = datetime.utcnow()
        ctx.log(
            EventKind.STAGE_TRANSITION,
            f"Advanced to stage '{ctx.current_stage.name}'",
        )
        return True
