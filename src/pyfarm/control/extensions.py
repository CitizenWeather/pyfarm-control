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
from pyfarm.control.spec.schema import ActuatorSpec, GrowSpec, NotificationsConfig


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
