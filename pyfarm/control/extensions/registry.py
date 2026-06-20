from __future__ import annotations

import sys
from typing import Callable, TypeVar

from pyfarm.control.actuators.base import BaseActuator
from pyfarm.control.actuators.logging_actuator import LoggingActuator
from pyfarm.control.spec.schema import ActuatorSpec, NotificationChannel, NotificationsSpec
from .protocols import Notifier

_ACTUATOR_REGISTRY: dict[str, type[BaseActuator]] = {}
_NOTIFIER_REGISTRY: dict[str, type] = {}

_A = TypeVar("_A", bound=type[BaseActuator])
_N = TypeVar("_N", bound=type)


def register_actuator(kind: str) -> Callable[[_A], _A]:
    """Register an actuator class for a spec `kind` (e.g. 'relay'). Constructor: cls(name, spec)."""

    def deco(cls: _A) -> _A:
        _ACTUATOR_REGISTRY[kind] = cls
        return cls

    return deco


def _load_iot_drivers() -> None:
    """Load hardware drivers from pyfarm-iot if available."""
    try:
        import pyfarm.iot  # noqa: F401 — triggers driver registration in pyfarm-iot registry
        from pyfarm.iot.registry import _ACTUATOR_REGISTRY as iot_registry

        # Copy registered hardware drivers into control's registry
        for kind, cls in iot_registry.items():
            if kind not in _ACTUATOR_REGISTRY:
                _ACTUATOR_REGISTRY[kind] = cls
    except ImportError:
        pass  # pyfarm-iot not installed; use logging fallback


def register_notifier(provider: str) -> Callable[[_N], _N]:
    """Register a notifier class for a channel `provider` (e.g. 'console'). Constructor: cls(name, channel)."""

    def deco(cls: _N) -> _N:
        _NOTIFIER_REGISTRY[provider] = cls
        return cls

    return deco


def build_actuator(name: str, spec: ActuatorSpec) -> BaseActuator:
    """Resolve spec.kind to a registered actuator class, falling back to LoggingActuator."""
    cls = _ACTUATOR_REGISTRY.get(spec.kind)
    if cls is None:
        print(
            f"No actuator registered for kind '{spec.kind}' — using LoggingActuator for '{name}'",
            file=sys.stderr,
        )
        return LoggingActuator(name)
    return cls(name, spec)


def build_notifier(name: str, channel: NotificationChannel) -> Notifier:
    """Resolve channel.provider to a registered notifier class, falling back to the console notifier."""
    cls = _NOTIFIER_REGISTRY.get(channel.provider)
    if cls is None:
        if channel.provider != "console":
            print(
                f"No notifier registered for provider '{channel.provider}' — "
                f"using console for channel '{name}'",
                file=sys.stderr,
            )
        cls = _console_notifier_cls()
    return cls(name, channel)


def build_notifiers(spec: NotificationsSpec) -> dict[str, Notifier]:
    """Build all configured channels into a name -> Notifier map."""
    return {name: build_notifier(name, channel) for name, channel in spec.channels.items()}


def _console_notifier_cls() -> type:
    """Fetch the console notifier, importing the providers module lazily to populate the registry."""
    cls = _NOTIFIER_REGISTRY.get("console")
    if cls is None:
        from pyfarm.control.extensions import notifiers  # noqa: F401 — triggers registration

        cls = _NOTIFIER_REGISTRY["console"]
    return cls


# Load hardware drivers from pyfarm-iot on module import (if available)
_load_iot_drivers()
