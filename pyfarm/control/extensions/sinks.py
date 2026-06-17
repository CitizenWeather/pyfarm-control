from __future__ import annotations

from pyfarm.core.models import ControlEvent, EventKind

from .protocols import Notifier


class NotifierSink:
    """
    EventSink that routes events to notification channels.

    Routing:
      - If the event carries an explicit `channels` list (alerts do), deliver to
        exactly those named channels.
      - Otherwise consult `default_routing[event.kind]` — this is what lets
        non-alert events (sensor failures, stage transitions) notify without
        being hard-wired to the alert path. Unrouted kinds are dropped.
    """

    def __init__(
        self,
        notifiers: dict[str, Notifier],
        default_routing: dict[EventKind, list[str]] | None = None,
    ):
        self._notifiers = notifiers
        self._default_routing = default_routing or {}

    async def handle(self, event: ControlEvent) -> None:
        channels = event.data.get("channels")
        if channels is None:
            channels = self._default_routing.get(event.kind, [])
        for channel_name in channels:
            notifier = self._notifiers.get(channel_name)
            if notifier is not None:
                await notifier.send(event)
