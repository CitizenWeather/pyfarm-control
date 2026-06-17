"""Evaluate alert rules each tick and fire notifications, honouring per-rule
cooldowns. Reuses pyfarm-core's :class:`SafeExpressionEvaluator` so the same
expression semantics (and validation) apply at runtime."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Callable

from pyfarm.control.alerts.channels.base import Notification, Notifier
from pyfarm.control.engine.context import ControlContext
from pyfarm.control.exceptions import SpecValidationError
from pyfarm.control.expr.evaluator import SafeExpressionEvaluator


def _now() -> datetime:
    return datetime.now(timezone.utc)


class AlertEvaluator:
    def __init__(
        self,
        notifier: Notifier,
        *,
        clock: Callable[[], datetime] = _now,
    ) -> None:
        self._notifier = notifier
        self._evaluator = SafeExpressionEvaluator()
        self._clock = clock
        self._last_fired: dict[int, datetime] = {}

    async def evaluate(self, ctx: ControlContext) -> list[str]:
        """Evaluate every alert against the context. Returns the messages of
        alerts that fired this tick."""
        now = self._clock()
        flat = ctx.as_flat_dict(now=now)
        fired: list[str] = []

        for index, alert in enumerate(ctx.spec.alerts):
            try:
                triggered = bool(self._evaluator.evaluate(alert.condition, flat))
            except SpecValidationError:
                # A referenced metric isn't available this tick (e.g. a sensor
                # that hasn't reported). Treat as not-triggered rather than
                # crashing the loop.
                continue
            if not triggered:
                continue
            if self._in_cooldown(index, alert.cooldown_minutes, now):
                continue

            self._last_fired[index] = now
            message = self._render(alert.message, ctx)
            await self._notifier.notify(
                alert.channels, Notification(alert.severity, message)
            )
            ctx.log_event("alert", message, severity=alert.severity)
            fired.append(message)
        return fired

    def _in_cooldown(self, index: int, cooldown_minutes: int, now: datetime) -> bool:
        if cooldown_minutes <= 0:
            return False
        last = self._last_fired.get(index)
        if last is None:
            return False
        return now - last < timedelta(minutes=cooldown_minutes)

    @staticmethod
    def _render(message: str, ctx: ControlContext) -> str:
        # Lightweight templating: {stage} and {duration} are commonly used.
        replacements = {
            "stage": ctx.current_stage.name,
            "duration": str(_now() - ctx.stage_entered_at),
        }
        for key, value in replacements.items():
            message = message.replace("{" + key + "}", value)
        return message
