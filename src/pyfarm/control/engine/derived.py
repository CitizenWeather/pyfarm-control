"""Derived environmental metrics computed from raw sensor readings."""

from __future__ import annotations

import math


def saturation_vapor_pressure_kpa(temp_c: float) -> float:
    """Saturation vapor pressure (kPa) via the Tetens equation."""
    return 0.6108 * math.exp(17.27 * temp_c / (temp_c + 237.3))


def compute_vpd(temp_c: float, humidity_rh: float) -> float:
    """Vapour pressure deficit (kPa) from temperature (C) and RH (0-1 ratio)."""
    return saturation_vapor_pressure_kpa(temp_c) * (1 - humidity_rh)


def compute_dew_point(temp_c: float, humidity_rh: float) -> float:
    """Magnus-formula dew point (C). ``humidity_rh`` is a 0-1 ratio."""
    rh = max(humidity_rh, 1e-6)
    a, b = 17.27, 237.7
    gamma = (a * temp_c) / (b + temp_c) + math.log(rh)
    return (b * gamma) / (a - gamma)
