"""Telegram bot channel. Network I/O via an injectable sender."""

from __future__ import annotations

import json

from pyfarm.control.alerts.channels.base import Channel, Notification
from pyfarm.control.alerts.channels.http import Sender, _urllib_sender


class TelegramChannel(Channel):
    def __init__(
        self,
        bot_token: str,
        chat_id: str,
        *,
        sender: Sender = _urllib_sender,
    ) -> None:
        self.url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        self.chat_id = chat_id
        self._sender = sender

    async def send(self, notification: Notification) -> None:
        payload = json.dumps(
            {
                "chat_id": self.chat_id,
                "text": f"[{notification.severity}] {notification.message}",
            }
        ).encode("utf-8")
        self._sender(self.url, payload, {"Content-Type": "application/json"})
