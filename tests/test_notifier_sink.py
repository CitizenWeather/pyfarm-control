import asyncio

from pyfarm.core.models import ControlEvent, EventKind
from pyfarm.control.extensions.sinks import NotifierSink


class FakeNotifier:
    def __init__(self, name):
        self.name = name
        self.received: list[ControlEvent] = []

    async def send(self, event: ControlEvent) -> None:
        self.received.append(event)


def test_alert_routes_to_explicit_channels():
    ops, phone = FakeNotifier("ops"), FakeNotifier("phone")
    sink = NotifierSink({"ops": ops, "phone": phone})
    event = ControlEvent(
        kind=EventKind.ALERT_FIRED, message="too hot", data={"channels": ["phone"]}
    )
    asyncio.run(sink.handle(event))
    assert [e.message for e in phone.received] == ["too hot"]
    assert ops.received == []  # not in the alert's channel list


def test_non_alert_event_routes_via_default_map():
    ops = FakeNotifier("ops")
    sink = NotifierSink({"ops": ops}, default_routing={EventKind.SENSOR_FAILURE: ["ops"]})
    event = ControlEvent(kind=EventKind.SENSOR_FAILURE, message="DHT22 dark")
    asyncio.run(sink.handle(event))
    assert [e.message for e in ops.received] == ["DHT22 dark"]


def test_unrouted_event_is_dropped():
    ops = FakeNotifier("ops")
    sink = NotifierSink({"ops": ops})  # no default routing
    event = ControlEvent(kind=EventKind.STAGE_TRANSITION, message="advanced")
    asyncio.run(sink.handle(event))
    assert ops.received == []


def test_unknown_channel_name_is_ignored():
    ops = FakeNotifier("ops")
    sink = NotifierSink({"ops": ops})
    event = ControlEvent(
        kind=EventKind.ALERT_FIRED, message="x", data={"channels": ["does-not-exist"]}
    )
    asyncio.run(sink.handle(event))  # must not raise
    assert ops.received == []
