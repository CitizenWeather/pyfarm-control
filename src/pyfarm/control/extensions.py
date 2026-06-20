"""Factory helpers for building actuators and notification channels from a GrowSpec.

Use these in the CLI or any integration that needs to construct live objects
from a loaded spec without wiring everything manually.
"""

from __future__ import annotations

from pyfarm.control.actuators.base import Actuator
from pyfarm.control.actuators.relay import RelayActuator
from pyfarm.control.actuators.pwm import PwmActuator
from pyfarm.control.alerts.channels.base import Channel, Notifier
from pyfarm.control.alerts.channels.ntfy import NtfyChannel
from pyfarm.control.alerts.channels.telegram import TelegramChannel
from pyfarm.control.alerts.channels.webhook import WebhookChannel
from pyfarm.control.alerts.evaluator import AlertEvaluator
from pyfarm.control.sensors.base import Sensor
from pyfarm.control.sensors.dht22 import (
    DHT22HumiditySensor,
    DHT22TemperatureSensor,
)
from pyfarm.control.sensors.fake import FakeSensor
from pyfarm.control.sensors.replay import ReplaySensor
from pyfarm.control.spec.schema import (
    ActuatorSpec,
    GrowSpec,
    NotificationsConfig,
    SensorSpec,
)


def build_sensor(name: str, spec: SensorSpec) -> Sensor:
    """Construct a live :class:`Sensor` from its :class:`SensorSpec`.

    Mirrors :func:`build_actuator`. ``dht22_*`` and ``analog`` kinds need a
    ``gpio`` pin; ``fake`` needs a constant ``value``; ``replay`` needs a ``csv``
    path. ``analog`` cannot be auto-built — it needs an ADC backend wired to your
    board — so construct :class:`AnalogSensor` manually and pass it in.
    """
    kind = spec.kind
    if kind == "dht22_temp":
        if spec.gpio is None:
            raise ValueError(f"Sensor {name!r}: dht22_temp requires a gpio pin")
        return DHT22TemperatureSensor(gpio=spec.gpio)
    if kind == "dht22_humidity":
        if spec.gpio is None:
            raise ValueError(f"Sensor {name!r}: dht22_humidity requires a gpio pin")
        return DHT22HumiditySensor(gpio=spec.gpio)
    if kind == "fake":
        if spec.value is None:
            raise ValueError(f"Sensor {name!r}: fake requires a constant 'value'")
        return FakeSensor(spec.metric, spec.value, unit=spec.unit)
    if kind == "replay":
        if not spec.csv:
            raise ValueError(f"Sensor {name!r}: replay requires a 'csv' path")
        values = _read_csv_column(spec.csv, spec.column or spec.metric)
        return ReplaySensor(spec.metric, values, unit=spec.unit)
    raise ValueError(
        f"Sensor {name!r}: cannot auto-build kind {kind!r}. For analog sensors, "
        "construct AnalogSensor with an ADC backend and pass it in."
    )


def _read_csv_column(path: str, column: str) -> list[float]:
    import csv
    from pathlib import Path

    with Path(path).open(newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or column not in reader.fieldnames:
            raise ValueError(
                f"Replay CSV {path!r} has no column {column!r} "
                f"(columns: {reader.fieldnames})"
            )
        values: list[float] = []
        for row in reader:
            raw = row[column]
            if raw is None or raw.strip() == "":
                continue
            values.append(float(raw))
    if not values:
        raise ValueError(f"Replay CSV {path!r} column {column!r} had no values")
    return values


def build_actuator(name: str, spec: ActuatorSpec) -> Actuator:
    """Construct a live :class:`Actuator` from its :class:`ActuatorSpec`.

    ``relay`` and ``pwm`` kinds require a ``gpio`` pin.
    ``mqtt`` cannot be auto-built (needs a client); raise :exc:`ValueError`.
    """
    if spec.kind == "relay":
        if spec.gpio is None:
            raise ValueError(f"Actuator {name!r}: relay kind requires a gpio pin")
        return RelayActuator(name, gpio=spec.gpio)
    if spec.kind == "pwm":
        if spec.gpio is None:
            raise ValueError(f"Actuator {name!r}: pwm kind requires a gpio pin")
        return PwmActuator(name, gpio=spec.gpio)
    raise ValueError(
        f"Actuator {name!r}: cannot auto-build kind {spec.kind!r}. "
        "For MQTT actuators, construct MqttActuator manually and pass it in."
    )


def build_notifiers(config: NotificationsConfig | None) -> dict[str, Channel]:
    """Build a ``{name: Channel}`` mapping from a :class:`NotificationsConfig`.

    Channel types are detected by the presence of keys in the per-channel dict:

    * ``provider: ntfy`` + ``topic`` → :class:`NtfyChannel`
    * ``bot_token`` + ``chat_id`` → :class:`TelegramChannel`
    * ``url`` → :class:`WebhookChannel`
    """
    if config is None:
        return {}
    channels: dict[str, Channel] = {}
    for name, cfg in config.channels.items():
        provider = str(cfg.get("provider", "")).lower()
        if provider == "ntfy":
            topic = cfg.get("topic")
            if not topic:
                raise ValueError(f"Notification channel {name!r}: ntfy provider requires 'topic'")
            channels[name] = NtfyChannel(topic=topic)
        elif "bot_token" in cfg and "chat_id" in cfg:
            channels[name] = TelegramChannel(
                bot_token=str(cfg["bot_token"]),
                chat_id=str(cfg["chat_id"]),
            )
        elif "url" in cfg:
            channels[name] = WebhookChannel(url=str(cfg["url"]))
        else:
            raise ValueError(
                f"Notification channel {name!r}: unrecognised config — "
                "expected provider='ntfy' with topic, 'bot_token'+'chat_id', or 'url'"
            )
    return channels


def build_alert_evaluator(
    channels: dict[str, Channel], spec: GrowSpec
) -> AlertEvaluator | None:
    """Return an :class:`AlertEvaluator` wired to ``channels``, or ``None``.

    Returns ``None`` when there are no channels or the spec has no alert rules,
    so callers can skip alert evaluation without extra ``if`` blocks.
    """
    if not channels or not spec.alerts:
        return None
    return AlertEvaluator(Notifier(channels))
