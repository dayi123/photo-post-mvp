from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


TemplatePackName = Literal["gpt-5.4", "gemini-3.1", "default"]
TemplatePackOverride = Literal["auto", "gpt-5.4", "gemini-3.1", "default"]


class JobState(str, Enum):
    RECEIVED = "RECEIVED"
    PREVIEW_1_EXPORTED = "PREVIEW_1_EXPORTED"
    PLAN_GENERATED = "PLAN_GENERATED"
    WAIT_USER_CONFIRM = "WAIT_USER_CONFIRM"
    ACTION_GENERATED = "ACTION_GENERATED"
    EDIT_APPLIED = "EDIT_APPLIED"
    PREVIEW_2_EXPORTED = "PREVIEW_2_EXPORTED"
    QUALITY_CHECKED = "QUALITY_CHECKED"
    FINAL_EXPORTED = "FINAL_EXPORTED"
    DELIVERED_ARCHIVED = "DELIVERED_ARCHIVED"
    FAILED = "FAILED"


class PlanStep(BaseModel):
    order: int = Field(ge=1, description="Execution order")
    title: str = Field(min_length=3, max_length=120)
    instruction: str = Field(min_length=5, max_length=500)


class Plan(BaseModel):
    summary: str = Field(min_length=10, max_length=500)
    goals: list[str] = Field(min_length=1, max_length=5)
    risks: list[str] = Field(default_factory=list, max_length=5)
    steps: list[PlanStep] = Field(min_length=1, max_length=10)
    estimated_minutes: int = Field(ge=1, le=60)


class AdjustmentOp(str, Enum):
    exposure = "exposure"
    contrast = "contrast"
    highlights = "highlights"
    shadows = "shadows"
    saturation = "saturation"
    temperature = "temperature"
    crop = "crop"
    straighten = "straighten"


class ActionAdjustment(BaseModel):
    op: AdjustmentOp
    value: float = Field(ge=-100.0, le=100.0)
    rationale: str = Field(min_length=5, max_length=200)


class Action(BaseModel):
    profile: str = Field(min_length=3, max_length=100)
    adjustments: list[ActionAdjustment] = Field(min_length=1, max_length=12)
    export_format: str = Field(default="jpg", pattern="^(jpg|jpeg|png)$")


class ReviewDecision(str, Enum):
    approved = "approved"
    revise = "revise"


class Review(BaseModel):
    decision: ReviewDecision
    approved: bool
    score: int = Field(ge=0, le=100)
    notes: list[str] = Field(min_length=1, max_length=5)
    next_focus: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def validate_consistency(self) -> "Review":
        if self.approved and self.decision != ReviewDecision.approved:
            raise ValueError("Approved reviews must use the approved decision.")
        if not self.approved and self.decision != ReviewDecision.revise:
            raise ValueError("Rejected reviews must use the revise decision.")
        return self


class ConfirmPlanRequest(BaseModel):
    confirmed: bool = True
    user_notes: str | None = Field(default=None, max_length=300)


class CreateJobFromPathRequest(BaseModel):
    path: str = Field(min_length=1, max_length=1000)
    desired_effect: str | None = Field(default=None, max_length=500)

    @field_validator("desired_effect", mode="before")
    @classmethod
    def normalize_desired_effect(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None


class JobRead(BaseModel):
    id: str
    state: JobState
    original_filename: str
    desired_effect: str | None
    review_rounds: int
    error_message: str | None
    preview_1_path: str | None
    preview_2_path: str | None
    final_path: str | None
    created_at: datetime
    updated_at: datetime
    result_ready: bool


class ResultEnvelope(BaseModel):
    job: JobRead
    plan: Plan | None = None
    action: Action | None = None
    review: Review | None = None
    audit_files: list[str] = Field(default_factory=list)


class AuditRecord(BaseModel):
    kind: str
    state: JobState
    payload: dict[str, Any]
    created_at: datetime


class RuntimeConfig(BaseModel):
    llm_provider: Literal["openai", "google", "custom"] = "openai"
    llm_model: str = Field(default="gpt-5.4", min_length=1, max_length=200)
    llm_api_key: str | None = Field(default=None, max_length=500)
    llm_base_url: str | None = Field(default=None, max_length=500)
    plan_template_pack: TemplatePackOverride = "auto"
    action_template_pack: TemplatePackOverride = "auto"
    editor_backend: Literal["stub", "davinci"] = "stub"
    davinci_cmd: str | None = Field(default=None, max_length=500)
    davinci_input_mode: Literal["stdin", "file"] = "stdin"
    davinci_timeout_seconds: int = Field(default=60, ge=1, le=600)

    @field_validator("llm_model")
    @classmethod
    def validate_model(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("llm_model must not be empty.")
        return normalized

    @field_validator("llm_api_key", "llm_base_url", "davinci_cmd", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None


class RuntimeConfigUpdate(BaseModel):
    llm_provider: Literal["openai", "google", "custom"] | None = None
    llm_model: str | None = Field(default=None, min_length=1, max_length=200)
    llm_api_key: str | None = Field(default=None, max_length=500)
    llm_base_url: str | None = Field(default=None, max_length=500)
    plan_template_pack: TemplatePackOverride | None = None
    action_template_pack: TemplatePackOverride | None = None
    editor_backend: Literal["stub", "davinci"] | None = None
    davinci_cmd: str | None = Field(default=None, max_length=500)
    davinci_input_mode: Literal["stdin", "file"] | None = None
    davinci_timeout_seconds: int | None = Field(default=None, ge=1, le=600)

    @field_validator("llm_model")
    @classmethod
    def validate_optional_model(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("llm_model must not be empty.")
        return normalized

    @field_validator("llm_api_key", "llm_base_url", "davinci_cmd", mode="before")
    @classmethod
    def normalize_optional_update_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return str(value).strip()


class RuntimeSettingsRead(BaseModel):
    llm_provider: Literal["openai", "google", "custom"]
    llm_model: str
    llm_api_key_masked: str | None = None
    llm_api_key_configured: bool
    llm_base_url: str | None = None
    plan_template_pack: TemplatePackOverride
    action_template_pack: TemplatePackOverride
    effective_plan_template_pack: TemplatePackName
    effective_action_template_pack: TemplatePackName
    editor_backend: Literal["stub", "davinci"]
    davinci_cmd: str | None = None
    davinci_input_mode: Literal["stdin", "file"]
    davinci_timeout_seconds: int


class SettingsTestResult(BaseModel):
    success: bool
    message: str
    provider: str | None = None
    model: str | None = None
    backend: str | None = None
    endpoint: str | None = None
    status_code: int | None = None
    detail: str | None = None
