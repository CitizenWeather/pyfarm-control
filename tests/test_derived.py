from pyfarm.biology.derived import (
    ph_drift_rate,
    fermentation_efficiency,
    doubling_time_hours,
)


def test_fermentation_efficiency():
    # 1.060 OG, 1.010 FG → ~83.33% apparent attenuation
    eff = fermentation_efficiency(1.060, 1.010)
    assert abs(eff - 83.33) < 1.0


def test_ph_drift_rate():
    # pH drops from 6.0 to 5.0 over 2 hours
    readings = [(0.0, 6.0), (3600.0, 5.5), (7200.0, 5.0)]
    rate = ph_drift_rate(readings)
    assert abs(rate - (-0.5)) < 0.01  # -0.5 pH/hour


def test_doubling_time():
    import math

    # OD doubles from 0.1 to 0.8 over 3 hours → ~1.0h doubling time
    readings = [(0.0, 0.1), (1.0, 0.2), (2.0, 0.4), (3.0, 0.8)]
    # Convert hours to seconds for the function
    readings_s = [(t * 3600, od) for t, od in readings]
    dt = doubling_time_hours(readings_s)
    assert dt is not None
    assert 0.9 < dt < 1.1
