from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from pyfarm.core.models import ControlEvent, SensorReading, Unit
from pyfarm.core.sensor import Sensor as CoreSensor
from pyfarm.core.storage import StorageBackend

if TYPE_CHECKING:
    from pyfarm.control.engine.context import ControlContext


# Re-export core's Sensor for backward compat and type checking
Sensor = CoreSensor

# Alias StorageBackend as Store for backward compat (control pre-dates StorageBackend naming)
Store = StorageBackend


@runtime_checkable
class Notifier(Protocol):
    """A delivery channel for control events (console, webhook, chat, ...)."""

    name: str

    async def send(self, event: ControlEvent) -> None: ...
