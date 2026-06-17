"""Runtime errors raised by the control engine.

Spec *loading* errors live in :class:`pyfarm.control.exceptions.SpecValidationError`
(shipped by pyfarm-core). These are the *runtime* counterparts.
"""

from __future__ import annotations


class ControlError(Exception):
    """Base class for control-engine runtime errors."""


class SensorReadError(ControlError):
    """Raised when a sensor cannot produce a reading."""


class ReplayExhausted(ControlError):
    """Raised by replay sensors when the recorded data is exhausted."""
