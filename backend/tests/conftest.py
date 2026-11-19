"""Shared fixtures.

The database fixtures connect to TEST_DATABASE_URL, run migrations once per session and
truncate every table between tests. There is no rollback-per-test: later features commit the
AI call log in its own transaction, so rollback would not isolate tests.
"""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import NoReturn

import httpx2
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from app.ai.sinks import DatabaseLogSink
from app.api.ai import get_ai_client
from app.api.applications import get_clock
from app.core.config import get_settings
from app.core.db import get_session
from app.main import app
from tests.fakes import NetworkBlocked

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


@pytest.fixture(autouse=True)
def _block_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """No test makes a network call. The Anthropic SDK sends requests through httpx2's
    HTTPTransport (or AsyncHTTPTransport for AsyncAnthropic); FastAPI's TestClient has its own
    in-process transport, so it is unaffected."""

    def blocked(self: httpx2.HTTPTransport, request: httpx2.Request) -> httpx2.Response:
        raise NetworkBlocked(f"a test tried to send {request.method} {request.url}")

    async def blocked_async(
        self: httpx2.AsyncHTTPTransport, request: httpx2.Request
    ) -> httpx2.Response:
        raise NetworkBlocked(f"a test tried to send {request.method} {request.url}")

    monkeypatch.setattr(httpx2.HTTPTransport, "handle_request", blocked)
    monkeypatch.setattr(httpx2.AsyncHTTPTransport, "handle_async_request", blocked_async)


@pytest.fixture
def db_session(test_engine: Engine) -> Iterator[Session]:
    factory = sessionmaker(bind=test_engine)
    with factory() as session:
        yield session


@pytest.fixture
def db_sink(test_engine: Engine) -> DatabaseLogSink:
    """The app's log sink, bound to the test database. It commits in its own session."""
    return DatabaseLogSink(sessionmaker(bind=test_engine))


def _real_ai_client_is_not_allowed() -> NoReturn:
    raise RuntimeError(
        "this test reached the real AI client: override get_ai_client with a FakeAIClient"
    )


@pytest.fixture
def client(db_session: Session, clock: FakeClock) -> Iterator[TestClient]:
    app.dependency_overrides[get_session] = lambda: db_session
    app.dependency_overrides[get_clock] = lambda: clock
    # A route test that needs the AI client must override this with a FakeAIClient. Without
    # this default it would get the real provider, whose log sink writes to the dev database's
    # append-only ai_calls, where a stray row cannot be deleted.
    app.dependency_overrides[get_ai_client] = _real_ai_client_is_not_allowed
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
