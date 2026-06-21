from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class DurationSpec(BaseModel):
    min_days: int
    max_days: int

    @model_validator(mode="after")
    def check_order(self) -> DurationSpec:
        if self.min_days > self.max_days:
            raise ValueError(f"min_days ({self.min_days}) must be <= max_days ({self.max_days})")
        return self


class ExitCondition(BaseModel):
    metric: str
    threshold: str  # e.g. ">= 0.95" or "starting_to_flatten"


class Setpoint(BaseModel):
    target: float
    unit: str | None = None
    tolerance: float


class LightSetpoint(BaseModel):
    schedule: str  # "12/12" or "0/24"
    intensity_lux: int | None = None


class VPDConstraint(BaseModel):
    target: float
    tolerance: float


class IrrigationSetpoint(BaseModel):
    trigger: str  # "time" | "sensor" | "et"
    duration_min: float
    daily_budget_l: float | None = None


class StageSetpoints(BaseModel):
    temperature: Setpoint | None = None
    humidity_rh: Setpoint | None = None
    co2_ppm: Setpoint | None = None
    light: LightSetpoint | None = None
    irrigation: IrrigationSetpoint | None = None


class Stage(BaseModel):
    name: str
    duration: DurationSpec
    exit_condition: ExitCondition
    setpoints: StageSetpoints
    vpd: VPDConstraint | None = None
    controls_disabled: list[str] = Field(default_factory=list)


class AlertSpec(BaseModel):
    condition: str
    severity: Literal["info", "warning", "critical"]
    message: str
    channels: list[str]
    cooldown_minutes: int = 30


class ActuatorSafety(BaseModel):
    max_on_seconds: int | None = None
    max_on_minutes: int | None = None
    min_off_seconds: int | None = None


class ActuatorSpec(BaseModel):
    kind: Literal["relay", "pwm", "mqtt"]
    gpio: int | None = None
    mqtt_topic: str | None = None
    pwm: bool = False
    interlock: str | None = None
    safety: ActuatorSafety | None = None


class NotificationChannel(BaseModel):
    provider: str
    topic: str | None = None
    bot_token: str | None = None
    chat_id: str | None = None


class NotificationsSpec(BaseModel):
    channels: dict[str, NotificationChannel] = Field(default_factory=dict)


class SpecMetadata(BaseModel):
    name: str
    species: str | None = None
    substrate: str | None = None
    author: str | None = None
    registry: str | None = None


class GrowSpec(BaseModel):
    spec_version: str
    kind: Literal["GrowSpec"]
    metadata: SpecMetadata
    stages: list[Stage]
    alerts: list[AlertSpec] = Field(default_factory=list)
    actuators: dict[str, ActuatorSpec] = Field(default_factory=dict)
    notifications: NotificationsSpec = Field(default_factory=NotificationsSpec)

    @model_validator(mode="after")
    def check_stages_non_empty(self) -> GrowSpec:
        if not self.stages:
            raise ValueError("GrowSpec must define at least one stage")
        return self
