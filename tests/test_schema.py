import pytest
from pydantic import ValidationError
from pyfarm.control.spec.schema import (
    GrowSpec, Stage, DurationSpec, ExitCondition, StageSetpoints, Setpoint
)


def _minimal_spec(**overrides) -> dict:
    base = {
        "spec_version": "1.0",
        "kind": "GrowSpec",
        "metadata": {"name": "test-spec"},
        "stages": [
            {
                "name": "colonisation",
                "duration": {"min_days": 14, "max_days": 28},
                "exit_condition": {"metric": "visual.colonisation_pct", "threshold": ">= 0.95"},
                "setpoints": {
                    "temperature": {"target": 24.0, "tolerance": 2.0},
                    "humidity_rh": {"target": 0.90, "tolerance": 0.05},
                },
            }
        ],
    }
    base.update(overrides)
    return base


def test_minimal_spec_valid():
    spec = GrowSpec.model_validate(_minimal_spec())
    assert spec.metadata.name == "test-spec"
    assert len(spec.stages) == 1


def test_empty_stages_rejected():
    with pytest.raises(ValidationError):
        GrowSpec.model_validate(_minimal_spec(stages=[]))


def test_duration_min_gt_max_rejected():
    data = _minimal_spec()
    data["stages"][0]["duration"] = {"min_days": 28, "max_days": 14}
    with pytest.raises(ValidationError):
        GrowSpec.model_validate(data)


def test_unknown_kind_rejected():
    data = _minimal_spec(kind="SomethingElse")
    with pytest.raises(ValidationError):
        GrowSpec.model_validate(data)
