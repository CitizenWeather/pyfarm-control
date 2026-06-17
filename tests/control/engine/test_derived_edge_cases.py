"""Edge-case tests for derived metric calculations (VPD, dew point)."""

import pytest

from pyfarm.control.engine.derived import (
    compute_dew_point,
    compute_vpd,
    saturation_vapor_pressure_kpa,
)


# -- saturation_vapor_pressure_kpa ------------------------------------------

def test_svp_normal_range():
    # At 20°C, SVP is approximately 2.338 kPa.
    assert abs(saturation_vapor_pressure_kpa(20.0) - 2.338) < 0.01


def test_svp_at_zero_celsius():
    assert abs(saturation_vapor_pressure_kpa(0.0) - 0.611) < 0.01


def test_svp_at_singularity_raises():
    with pytest.raises(ValueError, match="Tetens"):
        saturation_vapor_pressure_kpa(-237.3)


def test_svp_near_singularity_raises():
    with pytest.raises(ValueError, match="Tetens"):
        saturation_vapor_pressure_kpa(-237.3 + 1e-10)


# -- compute_vpd ------------------------------------------------------------

def test_vpd_at_full_saturation_is_zero():
    assert compute_vpd(20.0, 1.0) == 0.0


def test_vpd_typical_fruiting_value():
    # 18°C + 95% RH → VPD ≈ 0.103 kPa
    assert abs(compute_vpd(18.0, 0.95) - 0.103) < 0.01


def test_vpd_higher_temp_higher_vpd():
    assert compute_vpd(28.0, 0.8) > compute_vpd(18.0, 0.8)


# -- compute_dew_point -------------------------------------------------------

def test_dew_point_below_air_temperature():
    dew = compute_dew_point(20.0, 0.5)
    assert dew < 20.0


def test_dew_point_equals_air_at_saturation():
    # At 100% RH the dew point equals the air temperature.
    dew = compute_dew_point(20.0, 1.0)
    assert abs(dew - 20.0) < 0.1


def test_dew_point_at_magnus_singularity_raises():
    with pytest.raises(ValueError, match="Magnus"):
        compute_dew_point(-237.7, 0.5)


def test_dew_point_clamps_rh_to_avoid_log_zero():
    # humidity_rh=0 would make log(rh) → -inf; the function clamps to 1e-6.
    dew = compute_dew_point(20.0, 0.0)
    assert dew < 20.0  # should not crash
