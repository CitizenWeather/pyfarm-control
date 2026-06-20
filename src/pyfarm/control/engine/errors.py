"""Runtime errors raised by the control engine.

The hierarchy is owned by ``pyfarm-core`` (so sensor/actuator drivers and the
engine raise and catch the same types); it is re-exported here for backwards
compatibility with code that imports from ``pyfarm.control.engine.errors``.

Spec *loading* errors live in :class:`pyfarm.control.exceptions.SpecValidationError`.
"""

from __future__ import annotations

from pyfarm.core.errors import ControlError, ReplayExhausted, SensorReadError

__all__ = ["ControlError", "SensorReadError", "ReplayExhausted"]
