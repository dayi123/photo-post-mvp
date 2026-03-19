from __future__ import annotations

from functools import lru_cache

from sqlalchemy import inspect, text
from sqlmodel import Session, SQLModel, create_engine

from app.config import get_settings


@lru_cache(maxsize=1)
def get_engine():
    settings = get_settings()
    return create_engine(settings.database_url, connect_args={"check_same_thread": False})


def init_db() -> None:
    engine = get_engine()
    SQLModel.metadata.create_all(engine)
    inspector = inspect(engine)
    if "job" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("job")}
    if "runtime_settings_json" not in columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE job ADD COLUMN runtime_settings_json TEXT"))

    if "desired_effect" not in columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE job ADD COLUMN desired_effect TEXT"))


def get_session():
    with Session(get_engine()) as session:
        yield session
