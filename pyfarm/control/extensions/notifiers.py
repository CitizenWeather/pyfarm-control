from __future__ import annotations

import sys

from pyfarm.core.models import ControlEvent
from pyfarm.control.spec.schema import NotificationChannel

from .registry import register_notifier


@register_notifier("console")
class ConsoleNotifier:
    """
    Writes events to stderr. The default/fallback channel — always available,
    needs no credentials, and is what every unconfigured provider degrades to.
    """

    def __init__(self, name: str, channel: NotificationChannel):
        self.name = name
        self.channel = channel

    async def send(self, event: ControlEvent) -> None:
        print(f"[notify:{self.name}] {event.kind.value}: {event.message}", file=sys.stderr)
