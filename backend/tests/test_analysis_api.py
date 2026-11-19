"""The posting analysis endpoints."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.ai.schemas import PostingAnalysisOutput, Requirement, RequirementCategory
from app.ai.sinks import DatabaseLogSink
from app.ai.types import AIAPIError, AIConfigurationError, AIError
from app.api.ai import get_ai_client
from app.main import app
from app.models import AIFeature
from app.repositories.locks import GenerationLockRepository
from tests.conftest import FakeClock
from tests.fakes import FakeAIClient

APPLICATION = {
    "company": "Northwind Freight",
    "role": "Senior Backend Engineer",
    "source": "linkedin",
    "posting_text": "Build services that book, track and settle every load.",
}

OUTPUT = PostingAnalysisOutput(
    requirements=[
        Requirement(text="Ruby on Rails in production", category=RequirementCategory.MUST_HAVE),
        Requirement(text="React", category=RequirementCategory.NICE_TO_HAVE),
    ],
    keywords=["Ruby on Rails", "PostgreSQL", "ruby on rails"],
)


def use_ai(fake: FakeAIClient) -> None:
    app.dependency_overrides[get_ai_client] = lambda: fake


@pytest.fixture
def fake_ai(client: TestClient, db_sink: DatabaseLogSink) -> FakeAIClient:
    fake = FakeAIClient(db_sink, output=OUTPUT)
    use_ai(fake)
    return fake


@pytest.fixture
def application_id(client: TestClient) -> int:
    response = client.post("/applications", json=APPLICATION)
    assert response.status_code == 201, response.text
    return response.json()["id"]


@pytest.fixture
def other_session(test_engine: Engine) -> Iterator[Session]:
    with sessionmaker(bind=test_engine)() as session:
        yield session
        session.rollback()


def count(engine: Engine, table: str) -> int:
    with engine.connect() as conn:
        return conn.execute(text(f"SELECT count(*) FROM {table}")).scalar_one()


def analyze(client: TestClient, application_id: int) -> dict:
    response = client.post(f"/applications/{application_id}/analysis")
    assert response.status_code == 201, response.text
    return response.json()


# --- POST /applications/{id}/analysis -----------------------------------------------------------


def test_post_makes_one_ai_call_and_saves_a_draft(
    client: TestClient, fake_ai: FakeAIClient, application_id: int, test_engine: Engine
) -> None:
    response = client.post(f"/applications/{application_id}/analysis")

    assert response.status_code == 201
    body = response.json()
    assert body["id"] >= 1
    assert body["application_id"] == application_id
    assert body["status"] == "draft"
    assert body["prompt_version"] == "v1"
    assert body["reviewed_at"] is None
    assert body["created_at"]
    assert body["requirements"] == [
        {"text": "Ruby on Rails in production", "category": "must_have"},
        {"text": "React", "category": "nice_to_have"},
    ]
    assert body["keywords"] == ["ruby on rails", "postgresql"]
    assert len(fake_ai.calls) == 1
    assert count(test_engine, "ai_calls") == 1
    assert count(test_engine, "posting_analyses") == 1


def test_post_again_creates_a_new_row_and_keeps_the_old_one(
    client: TestClient, fake_ai: FakeAIClient, application_id: int, test_engine: Engine
) -> None:
    first = analyze(client, application_id)
    second = analyze(client, application_id)

    assert first["id"] != second["id"]
    assert count(test_engine, "posting_analyses") == 2


def test_post_for_an_unknown_application_is_404_and_calls_no_ai(
    client: TestClient, fake_ai: FakeAIClient
) -> None:
    response = client.post("/applications/999/analysis")

    assert response.status_code == 404
    assert fake_ai.calls == []


def test_post_while_one_is_running_is_409(
    client: TestClient,
    fake_ai: FakeAIClient,
    application_id: int,
    other_session: Session,
    test_engine: Engine,
) -> None:
    GenerationLockRepository(other_session).try_lock(AIFeature.POSTING_ANALYSIS, application_id)

    response = client.post(f"/applications/{application_id}/analysis")

    assert response.status_code == 409
    assert fake_ai.calls == []
    assert count(test_engine, "posting_analyses") == 0

    other_session.rollback()  # the first request finishes
    assert client.post(f"/applications/{application_id}/analysis").status_code == 201


@pytest.mark.parametrize("error", [AIAPIError, AIError])
def test_post_when_the_call_fails_is_502_with_the_failure_logged(
    client: TestClient,
    db_sink: DatabaseLogSink,
    application_id: int,
    test_engine: Engine,
    error: type[AIError],
) -> None:
    use_ai(FakeAIClient(db_sink, error=error))

    response = client.post(f"/applications/{application_id}/analysis")

    assert response.status_code == 502
    assert response.json() == {"detail": "The analysis failed. Try again."}
    assert count(test_engine, "posting_analyses") == 0
    with test_engine.connect() as conn:
        assert conn.execute(text("SELECT schema_valid FROM ai_calls")).scalar_one() is False


def test_post_without_an_api_key_is_503(client: TestClient, application_id: int) -> None:
    def not_configured() -> None:
        raise AIConfigurationError("ANTHROPIC_API_KEY is not set")

    app.dependency_overrides[get_ai_client] = not_configured

    response = client.post(f"/applications/{application_id}/analysis")

    assert response.status_code == 503
    assert "API_KEY" not in response.text


# --- GET /applications/{id}/analysis ------------------------------------------------------------


def test_get_without_an_analysis_is_200_null(client: TestClient, application_id: int) -> None:
    # No AI client is overridden here: reading must not need one.
    response = client.get(f"/applications/{application_id}/analysis")

    assert response.status_code == 200
    assert response.json() is None


def test_get_for_an_unknown_application_is_404(client: TestClient) -> None:
    assert client.get("/applications/999/analysis").status_code == 404


def test_get_returns_the_analysis_with_status_prompt_version_and_date(
    client: TestClient, fake_ai: FakeAIClient, application_id: int
) -> None:
    created = analyze(client, application_id)

    response = client.get(f"/applications/{application_id}/analysis")

    assert response.status_code == 200
    assert response.json() == created
    assert response.json()["prompt_version"] == "v1"


def test_get_shows_the_newest_analysis(
    client: TestClient, fake_ai: FakeAIClient, application_id: int, clock: FakeClock
) -> None:
    analyze(client, application_id)
    clock.advance(hours=1)
    newest = analyze(client, application_id)

    assert client.get(f"/applications/{application_id}/analysis").json()["id"] == newest["id"]


def test_get_does_not_let_a_rejected_one_hide_an_older_approved_one(
    client: TestClient, fake_ai: FakeAIClient, application_id: int, clock: FakeClock
) -> None:
    approved = analyze(client, application_id)
    assert client.post(f"/analyses/{approved['id']}/approve").status_code == 200
    clock.advance(hours=1)
    rejected = analyze(client, application_id)
    assert client.post(f"/analyses/{rejected['id']}/reject").status_code == 200

    shown = client.get(f"/applications/{application_id}/analysis").json()

    assert shown["id"] == approved["id"]
    assert shown["status"] == "approved"


# --- approve and reject -------------------------------------------------------------------------


def test_approve_sets_the_status_and_reviewed_at(
    client: TestClient, fake_ai: FakeAIClient, application_id: int, clock: FakeClock
) -> None:
    created = analyze(client, application_id)
    clock.advance(hours=1)

    response = client.post(f"/analyses/{created['id']}/approve")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "approved"
    assert body["reviewed_at"] and body["reviewed_at"] > created["created_at"]
    assert client.get(f"/applications/{application_id}/analysis").json()["status"] == "approved"


def test_reject_sets_the_status_and_reviewed_at(
    client: TestClient, fake_ai: FakeAIClient, application_id: int
) -> None:
    created = analyze(client, application_id)

    response = client.post(f"/analyses/{created['id']}/reject")

    assert response.status_code == 200
    assert response.json()["status"] == "rejected"
    assert response.json()["reviewed_at"]


def test_a_second_decision_is_409_and_changes_nothing(
    client: TestClient, fake_ai: FakeAIClient, application_id: int
) -> None:
    created = analyze(client, application_id)
    client.post(f"/analyses/{created['id']}/approve")

    assert client.post(f"/analyses/{created['id']}/reject").status_code == 409
    assert client.post(f"/analyses/{created['id']}/approve").status_code == 409
    assert client.get(f"/applications/{application_id}/analysis").json()["status"] == "approved"


def test_deciding_an_unknown_analysis_is_404(client: TestClient) -> None:
    # Neither route needs an AI client, so none is overridden.
    assert client.post("/analyses/999/approve").status_code == 404
    assert client.post("/analyses/999/reject").status_code == 404


def test_the_only_way_to_change_a_status_is_approve_or_reject(
    client: TestClient, fake_ai: FakeAIClient, application_id: int
) -> None:
    created = analyze(client, application_id)

    for method in ("put", "patch"):
        for path in (f"/analyses/{created['id']}", f"/applications/{application_id}/analysis"):
            response = getattr(client, method)(path, json={"status": "approved"})
            assert response.status_code in (404, 405)
    assert client.get(f"/applications/{application_id}/analysis").json()["status"] == "draft"


# --- OpenAPI ------------------------------------------------------------------------------------


def test_the_four_endpoints_appear_in_the_openapi_document(client: TestClient) -> None:
    paths = client.get("/openapi.json").json()["paths"]

    assert set(paths["/applications/{application_id}/analysis"]) == {"get", "post"}
    assert "post" in paths["/analyses/{analysis_id}/approve"]
    assert "post" in paths["/analyses/{analysis_id}/reject"]
    post = paths["/applications/{application_id}/analysis"]["post"]
    assert {"201", "404", "409", "502", "503"} <= set(post["responses"])
