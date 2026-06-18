import pytest
from pyfarm.biology.spec import BioSpec

KOMBUCHA = {
    "spec_version": "1.0",
    "kind": "BioSpec",
    "metadata": {
        "name": "Test Batch",
        "organism": "SCOBY",
        "substrate": "sweet tea",
        "target_ph": 3.2,
        "vessel_liters": 5.0,
    },
    "stages": [
        {
            "name": "primary_ferment",
            "duration": {"min_days": 7, "max_days": 14},
            "exit_condition": {"metric": "ph", "threshold": "< 3.5"},
            "setpoints": {"temperature_c": 24.0, "ph_target": 3.2},
        }
    ],
}


def test_valid_spec():
    spec = BioSpec.model_validate(KOMBUCHA)
    assert spec.kind == "BioSpec"
    assert spec.metadata.name == "Test Batch"
    assert len(spec.stages) == 1
    assert spec.stages[0].setpoints.temperature_c == 24.0


def test_extra_fields_rejected():
    bad = {**KOMBUCHA, "unknown_field": "x"}
    with pytest.raises(Exception):
        BioSpec.model_validate(bad)


def test_load_yaml(tmp_path):
    import yaml
    from pyfarm.biology.spec import load_bio_spec

    f = tmp_path / "test.bio.yaml"
    f.write_text(yaml.dump(KOMBUCHA))
    spec = load_bio_spec(str(f))
    assert spec.kind == "BioSpec"
