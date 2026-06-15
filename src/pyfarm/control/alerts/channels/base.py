"""Notification channels and the notifier that dispatches to them by name."""

from __future__ import annotations

import abc
from dataclasses import dataclass


@dataclass
class Notification:
    severity: str
    message: str


class Channel(abc.ABC):
    @abc.abstractmethod
    async def send(self, notification: Notification) -> None:
        raise NotImplementedError


class Notifier:
    """Routes a notification to the named channels, ignoring unknown names."""

    def __init__(self, channels: dict[str, Channel]) -> None:
        self._channels = channels

    async def notify(self, channel_names: list[str], notification: Notification) -> list[str]:
        delivered: list[str] = []
        for name in channel_names:
            channel = self._channels.get(name)
            if channel is None:
                continue
            await channel.send(notification)
            delivered.append(name)
        return delivered


class RecordingChannel(Channel):
    """Captures notifications in memory — for tests and replay."""

    def __init__(self) -> None:
        self.sent: list[Notification] = []

    async def send(self, notification: Notification) -> None:
        self.sent.append(notification)
