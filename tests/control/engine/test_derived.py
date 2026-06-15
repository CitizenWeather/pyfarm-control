from pyfarm.control.engine.derived import compute_dew_point, compute_vpd


def test_vpd_matches_known_value():
    # 18C + 95% RH ~ 0.1 kPa (initiation target in the reference spec).
    assert abs(compute_vpd(18.0, 0.95) - 0.103) < 0.01


def test_vpd_zero_at_saturation():
    assert compute_vpd(20.0, 1.0) == 0.0


def test_dew_point_below_air_temp():
    assert compute_dew_point(20.0, 0.5) < 20.0
