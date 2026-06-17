"""Actuator abstraction. Controllers compute commands; actuators apply them.

A *command* is either a bool (relay on/off) or a float in 0..1 (PWM duty).
"""

from __future__ import annotations

import abc
from typing import Union

Command = Union[bool, float]


class Actuator(abc.ABC):
    def __init__(self, name: str) -> None:
        self.name = name

    @abc.abstractmethod
    async def apply(self, command: Command) -> None:
        """Drive the actuator to ``command``."""
        raise NotImplementedError

    async def off(self) -> None:
        """Force the actuator off. Default implementation applies ``False``."""
        await self.apply(False)

    @staticmethod
    def is_on(command: Command) -> bool:
        """Interpret a command as a boolean on/off state."""
        if isinstance(command, bool):
            return command
        return float(command) > 0.0
