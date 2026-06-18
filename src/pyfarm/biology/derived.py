"""Pure-math biology metric functions for pyfarm-biology.

All functions accept time-series readings as lists of (timestamp_epoch_seconds, value)
tuples and return scalar results. Linear regression is used where trends are estimated.
"""

from __future__ import annotations

import math


def _linear_regression(xs: list[float], ys: list[float]) -> tuple[float, float]:
    """Return (slope, intercept) for a simple least-squares linear regression."""
    n = len(xs)
    if n < 2:
        raise ValueError("Need at least 2 data points for linear regression")
    sum_x = sum(xs)
    sum_y = sum(ys)
    sum_xx = sum(x * x for x in xs)
    sum_xy = sum(x * y for x, y in zip(xs, ys))
    denom = n * sum_xx - sum_x * sum_x
    if denom == 0:
        raise ValueError("All x values are identical — cannot compute slope")
    slope = (n * sum_xy - sum_x * sum_y) / denom
    intercept = (sum_y - slope * sum_x) / n
    return slope, intercept


def ph_drift_rate(readings: list[tuple[float, float]]) -> float:
    """pH drift per hour using linear regression.

    Args:
        readings: List of (timestamp_epoch_seconds, ph_value) tuples.

    Returns:
        Slope in pH units per hour (negative = acidification).
    """
    if len(readings) < 2:
        raise ValueError("Need at least 2 pH readings")
    xs = [t / 3600.0 for t, _ in readings]  # convert seconds to hours
    ys = [ph for _, ph in readings]
    slope, _ = _linear_regression(xs, ys)
    return slope


def doubling_time_hours(od_readings: list[tuple[float, float]]) -> float | None:
    """Estimated cell doubling time from OD600 readings using log-linear regression.

    Fits ln(OD) = mu * t + b, then doubling_time = ln(2) / mu.

    Args:
        od_readings: List of (timestamp_epoch_seconds, od600_value) tuples.

    Returns:
        Doubling time in hours, or None if growth rate is non-positive.
    """
    if len(od_readings) < 2:
        return None
    valid = [(t, od) for t, od in od_readings if od > 0]
    if len(valid) < 2:
        return None
    xs = [t / 3600.0 for t, _ in valid]  # seconds → hours
    ys = [math.log(od) for _, od in valid]
    slope, _ = _linear_regression(xs, ys)  # slope = specific growth rate (1/hr)
    if slope <= 0:
        return None
    return math.log(2) / slope


def fermentation_efficiency(initial_gravity: float, final_gravity: float) -> float:
    """Apparent attenuation percentage — fraction of sugar consumed.

    Apparent attenuation (%) = (OG - FG) / (OG - 1.0) * 100

    Args:
        initial_gravity: Original gravity (e.g. 1.060).
        final_gravity:   Final gravity   (e.g. 1.010).

    Returns:
        Apparent attenuation as a percentage (0–100+).
    """
    og_points = initial_gravity - 1.0
    if og_points == 0:
        raise ValueError("Initial gravity must be greater than 1.0")
    fg_points = final_gravity - 1.0
    return (og_points - fg_points) / og_points * 100.0


def co2_production_rate(gravity_readings: list[tuple[float, float]]) -> float:
    """Estimated CO2 production rate in g/L/hr from gravity drop.

    Uses the approximation: each 0.001 SG drop ≈ 2.0425 g/L CO2 produced,
    then divides by elapsed time.

    Args:
        gravity_readings: List of (timestamp_epoch_seconds, specific_gravity) tuples.

    Returns:
        CO2 production rate in g/L/hr (positive value).
    """
    if len(gravity_readings) < 2:
        raise ValueError("Need at least 2 gravity readings")
    xs = [t / 3600.0 for t, _ in gravity_readings]  # seconds → hours
    ys = [sg for _, sg in gravity_readings]
    slope, _ = _linear_regression(xs, ys)  # SG drop per hour (typically negative)
    # Convert SG/hr to g CO2/L/hr: 1 SG unit = 2042.5 g/L CO2 equivalent
    co2_rate = -slope * 2042.5
    return co2_rate
