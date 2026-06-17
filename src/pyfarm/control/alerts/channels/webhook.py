"""Generic JSON webhook channel."""

from __future__ import annotations

import json

from pyfarm.control.alerts.channels.base import Channel, Notification
from pyfarm.control.alerts.channels.http import Sender, _urllib_sender


class WebhookChannel(Channel):
    def __init__(self, url: str, *, sender: Sender = _urllib_sender) -> None:
        self.url = url
        self._sender = sender

    async def send(self, notification: Notification) -> None:
        payload = json.dumps(
            {"severity": notification.severity, "message": notification.message}
        ).encode("utf-8")
        self._sender(self.url, payload, {"Content-Type": "application/json"})
