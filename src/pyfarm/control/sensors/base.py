"""Sensor abstraction.

The ``Sensor`` contract is owned by ``pyfarm-core`` so real and simulated
sensors — wherever they live — implement the same interface and the runner is
agnostic to where readings come from. Re-exported here for the drivers in this
package and for backwards compatibility.
"""

from __future__ import annotations

from pyfarm.core.sensor import Sensor

__all__ = ["Sensor"]
