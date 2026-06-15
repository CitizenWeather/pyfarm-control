"""ntfy.sh push channel. Network I/O via an injectable sender (stdlib by
default) so the module imports without third-party HTTP libs."""

from __future__ import annotations

from typing import Callable
from urllib import request

from pyfarm.control.alerts.channels.base import Channel, Notification

# A sender takes (url, data_bytes, headers) and performs the POST.
Sender = Callable[[str, bytes, dict[str, str]], None]


def _urllib_sender(url: str, data: bytes, headers: dict[str, str]) -> None:  # pragma: no cover - network
    req = request.Request(url, data=data, headers=headers, method="POST")
    request.urlopen(req, timeout=10).close()


class NtfyChannel(Channel):
    def __init__(
        self,
        topic: str,
        *,
        server: str = "https://ntfy.sh",
        sender: Sender = _urllib_sender,
    ) -> None:
        self.url = f"{server.rstrip('/')}/{topic}"
        self._sender = sender

    async def send(self, notification: Notification) -> None:
        headers = {
            "Title": f"pyfarm {notification.severity}",
            "Priority": "urgent" if notification.severity == "critical" else "default",
        }
        self._sender(self.url, notification.message.encode("utf-8"), headers)
