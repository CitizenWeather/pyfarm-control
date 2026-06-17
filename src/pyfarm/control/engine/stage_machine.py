"""Stage transitions.

Biology drives transitions: a stage's ``exit_condition`` is the trigger, not
the calendar. ``duration`` is a safety net — we emit an event if a stage runs
past ``max_days`` without meeting its exit condition, and note when one exits
before ``min_days``.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Callable

from pyfarm.control.engine.context import ControlContext
from pyfarm.control.exceptions import SpecValidationError
from pyfarm.control.expr.evaluator import SafeExpressionEvaluator

_COMPARISON_PREFIXES = (">=", "<=", "==", "!=", ">", "<")
_COMPARISON_RE = re.compile(r"^(>=|<=|==|!=|>|<)\s*-?\d+(\.\d+)?$")


def _now() -> datetime:
    return datetime.now(timezone.utc)


class StageMachine:
    def __init__(
        self,
        *,
        clock: Callable[[], datetime] = _now,
        day_seconds: float = 86400.0,
    ) -> None:
        self._evaluator = SafeExpressionEvaluator()
        self._clock = clock
        self._day_seconds = day_seconds
        self._overdue_logged = -1

    def elapsed_days(self, ctx: ControlContext) -> float:
        return (self._clock() - ctx.stage_entered_at).total_seconds() / self._day_seconds

    def exit_condition_met(self, ctx: ControlContext) -> bool:
        stage = ctx.current_stage
        metric = stage.exit_condition.metric
        threshold = stage.exit_condition.threshold.strip()
        value = ctx.get_metric(metric)
        if value is None:
            return False

        if threshold.startswith(_COMPARISON_PREFIXES):
            if not _COMPARISON_RE.match(threshold):
                return False
            expression = f"{metric} {threshold}"
            try:
                return bool(
                    self._evaluator.evaluate(expression, ctx.as_flat_dict())
                )
            except SpecValidationError:
                return False
        # Enum / string literal threshold, e.g. "starting_to_flatten".
        return str(value) == threshold

    async def evaluate(self, ctx: ControlContext) -> bool:
        """Advance the stage if its exit condition is met. Returns True if a
        transition happened."""
        elapsed = self.elapsed_days(ctx)
        stage = ctx.current_stage

        if self.exit_condition_met(ctx):
            if ctx.is_final_stage:
                return False
            note = ""
            if elapsed < stage.duration.min_days:
                note = (
                    f" (early: {elapsed:.1f}d < min {stage.duration.min_days}d)"
                )
            previous = stage.name
            ctx.current_stage_index += 1
            ctx.stage_entered_at = self._clock()
            self._overdue_logged = -1
            ctx.log_event(
                "stage_advanced",
                f"Advanced {previous!r} -> {ctx.current_stage.name!r}{note}",
                from_stage=previous,
                to_stage=ctx.current_stage.name,
            )
            return True

        if (
            elapsed > stage.duration.max_days
            and self._overdue_logged != ctx.current_stage_index
        ):
            self._overdue_logged = ctx.current_stage_index
            ctx.log_event(
                "stage_overdue",
                f"Stage {stage.name!r} past max {stage.duration.max_days}d "
                f"({elapsed:.1f}d) without meeting exit condition "
                f"{stage.exit_condition.metric} {stage.exit_condition.threshold}",
                stage=stage.name,
            )
        return False
