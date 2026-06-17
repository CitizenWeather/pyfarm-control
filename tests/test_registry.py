import pytest

from pyfarm.control.actuators.base import BaseActuator
from pyfarm.control.actuators.logging_actuator import LoggingActuator
from pyfarm.control.extensions import build_actuator, build_notifier, build_notifiers, register_actuator
from pyfarm.control.extensions.registry import _ACTUATOR_REGISTRY
from pyfarm.control.extensions.notifiers import ConsoleNotifier
from pyfarm.control.spec.schema import ActuatorSpec, NotificationChannel, NotificationsSpec


def test_unregistered_kind_falls_back_to_logging_actuator():
    actuator = build_actuator("misting", ActuatorSpec(kind="relay", gpio=17))
    assert isinstance(actuator, LoggingActuator)
    assert actuator.name == "misting"


def test_registered_kind_resolves_to_class():
    @register_actuator("relay")
    class FakeRelay(BaseActuator):
        def __init__(self, name, spec):
            super().__init__(name)
            self.spec = spec

        async def on(self): ...
        async def off(self): ...

    try:
        actuator = build_actuator("fan", ActuatorSpec(kind="relay", gpio=5))
        assert isinstance(actuator, FakeRelay)
        assert actuator.spec.gpio == 5
    finally:
        _ACTUATOR_REGISTRY.pop("relay", None)


def test_build_notifier_console():
    n = build_notifier("ops", NotificationChannel(provider="console"))
    assert isinstance(n, ConsoleNotifier)
    assert n.name == "ops"


def test_build_notifier_unknown_provider_falls_back_to_console():
    n = build_notifier("phone", NotificationChannel(provider="telegram", bot_token="x"))
    assert isinstance(n, ConsoleNotifier)


def test_build_notifiers_maps_all_channels():
    spec = NotificationsSpec(
        channels={
            "ops": NotificationChannel(provider="console"),
            "phone": NotificationChannel(provider="webhook", topic="t"),
        }
    )
    notifiers = build_notifiers(spec)
    assert set(notifiers) == {"ops", "phone"}
    assert all(hasattr(n, "send") for n in notifiers.values())
