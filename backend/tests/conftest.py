"""Shared fixtures.

The database fixtures connect to TEST_DATABASE_URL, run migrations once per session and
truncate every table between tests. There is no rollback-per-test: later features commit the
AI call log in its own transaction, so rollback would not isolate tests.
"""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from app.api.applications import get_clock
from app.core.config import get_settings
from app.core.db import get_session
from app.main import app

BACKEND_DIR = Path(__file__).resolve().parent.parent


class FakeClock:
    """A clock the test controls. Calling it returns "now"; advance() moves it forward."""

    def __init__(self) -> None:
        self.now = datetime(2026, 11, 18, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **delta: float) -> None:
        self.now += timedelta(**delta)


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture(scope="session")
def alembic_config() -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    config.set_main_option("sqlalchemy.url", get_settings().test_database_url)
    return config


@pytest.fixture(scope="session")
def test_engine(alembic_config: Config) -> Iterator[Engine]:
    command.upgrade(alembic_config, "head")

    engine = create_engine(get_settings().test_database_url)
    yield engine
    engine.dispose()


@pytest.fixture(autouse=True)
def _truncate_tables(test_engine: Engine) -> Iterator[None]:
    yield
    tables = [t for t in inspect(test_engine).get_table_names() if t != "alembic_version"]
    if tables:
        names = ", ".join(f'"{t}"' for t in tables)
        with test_engine.begin() as conn:
            conn.execute(text(f"TRUNCATE {names} RESTART IDENTITY CASCADE"))


@pytest.fixture
def db_session(test_engine: Engine) -> Iterator[Session]:
    factory = sessionmaker(bind=test_engine)
    with factory() as session:
        yield session


@pytest.fixture
def client(db_session: Session, clock: FakeClock) -> Iterator[TestClient]:
    app.dependency_overrides[get_session] = lambda: db_session
    app.dependency_overrides[get_clock] = lambda: clock
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
