from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field


class Settings(BaseModel):
    project_name: str = "photo-post-mvp"
    database_url: str = Field(default="sqlite:///./photo_post_mvp.db")
    data_dir: Path = Field(default=Path("data"))
    max_review_rounds: int = 3
    default_llm_provider: str = "openai"
    default_llm_model: str = "gemini-3.1-pro-preview"
    default_llm_api_key: str | None = None
    default_llm_base_url: str | None = "https://new.lemonapi.site/v1"
    default_editor_backend: str = "stub"
    default_davinci_cmd: str | None = None
    default_davinci_input_mode: str = "stdin"
    default_davinci_timeout_seconds: int = 60

    @property
    def runtime_config_path(self) -> Path:
        return self.data_dir / "runtime_config.json"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        database_url=os.getenv("PHOTO_POST_DATABASE_URL", "sqlite:///./photo_post_mvp.db"),
        data_dir=Path(os.getenv("PHOTO_POST_DATA_DIR", "data")),
        max_review_rounds=int(os.getenv("PHOTO_POST_MAX_REVIEW_ROUNDS", "3")),
        default_llm_provider=os.getenv("PHOTO_POST_LLM_PROVIDER", "openai"),
        default_llm_model=os.getenv("PHOTO_POST_LLM_MODEL", "gemini-3.1-pro-preview"),
        default_llm_api_key=os.getenv("PHOTO_POST_LLM_API_KEY"),
        default_llm_base_url=os.getenv("PHOTO_POST_LLM_BASE_URL", "https://new.lemonapi.site/v1"),
        default_editor_backend=os.getenv("PHOTO_POST_EDITOR", "stub"),
        default_davinci_cmd=os.getenv("PHOTO_POST_DAVINCI_CMD"),
        default_davinci_input_mode=os.getenv("PHOTO_POST_DAVINCI_INPUT_MODE", "stdin"),
        default_davinci_timeout_seconds=int(os.getenv("PHOTO_POST_DAVINCI_TIMEOUT_SECONDS", "60")),
    )
