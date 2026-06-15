"""MQTT actuator for Home Assistant / Tasmota / ESPHome targets.

The MQTT client is injected (any object with ``publish(topic, payload)``), so
this module imports without ``paho-mqtt`` present.
"""

from __future__ import annotations

from typing import Protocol

from pyfarm.control.actuators.base import Actuator, Command


class MqttClient(Protocol):
    def publish(self, topic: str, payload: str) -> object: ...


class MqttActuator(Actuator):
    def __init__(
        self,
        name: str,
        topic: str,
        client: MqttClient,
        *,
        on_payload: str = "ON",
        off_payload: str = "OFF",
    ) -> None:
        super().__init__(name)
        self.topic = topic
        self._client = client
        self._on_payload = on_payload
        self._off_payload = off_payload

    async def apply(self, command: Command) -> None:
        if isinstance(command, bool):
            payload = self._on_payload if command else self._off_payload
        else:
            payload = str(command)
        self._client.publish(self.topic, payload)
