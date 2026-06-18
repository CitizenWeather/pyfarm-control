"""BioSpec — fermentation, microbial culture, lab incubation, and assay run specs."""

from __future__ import annotations

from typing import Literal, Any

from pydantic import BaseModel, Field, ConfigDict

from pyfarm.control.spec.base import (
    BaseSpec,
    BaseStage,
    BaseActuatorSpec,
    BaseSpecMetadata,
    DurationSpec,
    ExitConditionSpec,
    AlertRule,
    ActuatorSafety,
)


class BioSetpoints(BaseModel):
    model_config = ConfigDict(extra="forbid")

    temperature_c: float | None = None
    ph_target: float | None = None
    ph_tolerance: float = 0.2
    dissolved_oxygen_ppm: float | None = None
    agitation_rpm: int | None = None
    pressure_kpa: float | None = None
    co2_pct: float | None = None


class BioStage(BaseStage):
    model_config = ConfigDict(extra="forbid")

    setpoints: BioSetpoints = Field(default_factory=BioSetpoints)
    inoculation_temp_c: float | None = None  # stage-specific override


class BioMetadata(BaseSpecMetadata):
    model_config = ConfigDict(extra="forbid")

    organism: str | None = None          # e.g. "Acetobacter xylinum", "L. bulgaricus"
    substrate: str | None = None         # e.g. "sweet tea", "whole milk"
    target_ph: float | None = None
    target_gravity: float | None = None  # final SG for fermentation
    vessel_liters: float | None = None


class BioActuatorSpec(BaseActuatorSpec):
    model_config = ConfigDict(extra="forbid")
    # kind: agitator | heater | chiller | nutrient_pump | air_sparger | harvest_valve | ph_doser


class BioSpec(BaseSpec):
    model_config = ConfigDict(extra="forbid")

    spec_version: Literal["1.0"]
    kind: Literal["BioSpec"]
    metadata: BioMetadata
    stages: list[BioStage]
    alerts: list[AlertRule] = []
    actuators: dict[str, BioActuatorSpec] = {}
    notifications: Any = None


def load_bio_spec(path: str) -> BioSpec:
    """Load and validate a .bio.yaml file, returning a BioSpec instance."""
    import yaml

    with open(path) as f:
        data = yaml.safe_load(f)
    return BioSpec.model_validate(data)
