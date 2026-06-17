import pytest
from pyfarm.control.spec.schema import GrowSpec
from pyfarm.control.spec.validator import validate_spec, SpecValidationError


def _load(data: dict) -> GrowSpec:
    return GrowSpec.model_validate(data)


def _base_stage(name="colonisation", **kw) -> dict:
    s = {
        "name": name,
        "duration": {"min_days": 14, "max_days": 28},
        "exit_condition": {"metric": "visual.colonisation_pct", "threshold": ">= 0.95"},
        "setpoints": {
            "temperature": {"target": 24.0, "tolerance": 2.0},
            "humidity_rh": {"target": 0.90, "tolerance": 0.05},
        },
    }
    s.update(kw)
    return s


def _minimal() -> dict:
    return {
        "spec_version": "1.0",
        "kind": "GrowSpec",
        "metadata": {"name": "test"},
        "stages": [_base_stage()],
    }


def test_valid_spec_passes():
    spec = _load(_minimal())
    validate_spec(spec)  # should not raise


def test_duplicate_stage_names_rejected():
    data = _minimal()
    data["stages"].append(_base_stage(name="colonisation"))
    spec = _load(data)
    with pytest.raises(SpecValidationError, match="unique"):
        validate_spec(spec)


def test_vpd_consistency_ok():
    data = _minimal()
    # 18C + 95% RH -> VPD ~0.103 kPa; target 0.11 is within tolerance 0.1
    data["stages"][0]["setpoints"]["temperature"]["target"] = 18.0
    data["stages"][0]["setpoints"]["humidity_rh"]["target"] = 0.95
    data["stages"][0]["vpd"] = {"target": 0.11, "tolerance": 0.1}
    spec = _load(data)
    validate_spec(spec)  # should not raise


def test_vpd_consistency_rejected():
    data = _minimal()
    data["stages"][0]["setpoints"]["temperature"]["target"] = 24.0
    data["stages"][0]["setpoints"]["humidity_rh"]["target"] = 0.90
    # Computed VPD at 24C+90%RH is ~0.30 kPa; claiming 0.05 should fail
    data["stages"][0]["vpd"] = {"target": 0.05, "tolerance": 0.02}
    spec = _load(data)
    with pytest.raises(SpecValidationError, match="inconsistent"):
        validate_spec(spec)


def test_bad_alert_expression_rejected():
    data = _minimal()
    data["alerts"] = [{
        "condition": "temperature.current > __import__('os').system('rm -rf /')",
        "severity": "critical",
        "message": "bad",
        "channels": [],
    }]
    spec = _load(data)
    with pytest.raises(SpecValidationError):
        validate_spec(spec)


def test_bad_interlock_syntax_rejected():
    data = _minimal()
    data["actuators"] = {
        "misting": {"kind": "relay", "gpio": 17, "interlock": "humidity_rh.current @@@ 0.95"}
    }
    spec = _load(data)
    with pytest.raises(SpecValidationError, match="Syntax error"):
        validate_spec(spec)
