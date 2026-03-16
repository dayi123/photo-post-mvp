from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel

from app.schemas import JobState


class Job(SQLModel, table=True):
    id: str = Field(primary_key=True, index=True)
    original_filename: str
    state: JobState = Field(default=JobState.RECEIVED, index=True)
    runtime_settings_json: Optional[str] = None
    plan_json: Optional[str] = None
    action_json: Optional[str] = None
    review_json: Optional[str] = None
    preview_1_path: Optional[str] = None
    preview_2_path: Optional[str] = None
    final_path: Optional[str] = None
    original_path: Optional[str] = None
    review_rounds: int = 0
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
