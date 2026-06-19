"""Actuator abstraction. Controllers compute commands; actuators apply them.

A *command* is either a bool (relay on/off) or a float in 0..1 (PWM duty). The
``Actuator`` contract is owned by ``pyfarm-core`` and re-exported here for the
drivers in this package and for backwards compatibility.
"""

from __future__ import annotations

from pyfarm.core.actuator import Actuator, Command

__all__ = ["Actuator", "Command"]
