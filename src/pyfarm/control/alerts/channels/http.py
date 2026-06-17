"""Shared HTTP utility for notification channel implementations."""

from __future__ import annotations

from typing import Callable
from urllib import request

Sender = Callable[[str, bytes, dict[str, str]], None]


def _urllib_sender(url: str, data: bytes, headers: dict[str, str]) -> None:  # pragma: no cover - network
    req = request.Request(url, data=data, headers=headers, method="POST")
    request.urlopen(req, timeout=10).close()
