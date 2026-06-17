import asyncio

from pyfarm.control.actuators.logging import LoggingActuator
from pyfarm.control.actuators.relay import RelayActuator


def test_logging_actuator_records_only_transitions():
    act = LoggingActuator("misting")
    asyncio.run(_drive(act, [False, True, True, False, True]))
    states = [act.is_on(c.command) for c in act.history]
    assert states == [True, False, True]  # only state changes logged


def test_logging_actuator_log_every():
    act = LoggingActuator("misting", log_every=True)
    asyncio.run(_drive(act, [True, True, False]))
    assert len(act.history) == 3


def test_relay_uses_injected_backend():
    calls = []
    act = RelayActuator("heater", gpio=22, backend=lambda pin, level: calls.append((pin, level)))
    asyncio.run(act.apply(True))
    asyncio.run(act.off())
    assert calls == [(22, True), (22, False)]
    assert act.state is False


def test_relay_active_low_inverts_level():
    calls = []
    act = RelayActuator(
        "heater", gpio=5, active_high=False, backend=lambda pin, level: calls.append(level)
    )
    asyncio.run(act.apply(True))
    assert calls == [False]  # active-low: ON drives the pin low


async def _drive(act, commands):
    for c in commands:
        await act.apply(c)
