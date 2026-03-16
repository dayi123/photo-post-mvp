from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel

from app.config import get_settings
from app.db import get_engine
from app.main import create_app


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "test.db"
    data_dir = tmp_path / "data"
    monkeypatch.setenv("PHOTO_POST_DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("PHOTO_POST_DATA_DIR", str(data_dir))

    get_settings.cache_clear()
    get_engine.cache_clear()

    app = create_app()
    with TestClient(app) as test_client:
        engine = get_engine()
        SQLModel.metadata.drop_all(engine)
        SQLModel.metadata.create_all(engine)
        yield test_client

    get_settings.cache_clear()
    get_engine.cache_clear()
