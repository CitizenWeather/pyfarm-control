from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from pyfarm.core.models import ControlEvent, SensorReading, Unit

if TYPE_CHECKING:
    from pyfarm.control.engine.context import ControlContext


@runtime_checkable
class Sensor(Protocol):
    """A source of readings for one metric. Implemented by ReplaySensor and hardware sensors."""

    metric: str
    unit: Unit

    async def read(self) -> SensorReading: ...

    @property
    def exhausted(self) -> bool: ...


@runtime_checkable
class Store(Protocol):
    """Persists context snapshots for crash recovery. Called once per tick by the runner."""

    async def write_snapshot(self, ctx: "ControlContext") -> None: ...


@runtime_checkable
class Notifier(Protocol):
    """A delivery channel for control events (console, webhook, chat, ...)."""

    name: str

    async def send(self, event: ControlEvent) -> None: ...
