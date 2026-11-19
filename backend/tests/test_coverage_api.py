"""GET /applications/{id}/coverage."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app.ai.schemas import PostingAnalysisOutput, Requirement, RequirementCategory
from app.ai.sinks import DatabaseLogSink
from app.api.ai import get_ai_client
from app.main import app
from tests.fakes import FakeAIClient

APPLICATION = {
    "company": "Northwind Freight",
    "role": "Senior Backend Engineer",
    "source": "linkedin",
    "posting_text": "Build services that book, track and settle every load.",
}

KEYWORDS = ["ruby on rails", "postgresql", "ci/cd", "react"]
BASE_RESUME = "Ruby on Rails and PostgreSQL services. Led a small team."


def analyze(client: TestClient, sink: DatabaseLogSink, application_id: int, keywords: list[str]):
    fake = FakeAIClient(
        sink,
        output=PostingAnalysisOutput(
            requirements=[Requirement(text="Anything", category=RequirementCategory.MUST_HAVE)],
            keywords=keywords,
        ),
    )
    app.dependency_overrides[get_ai_client] = lambda: fake
    response = client.post(f"/applications/{application_id}/analysis")
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def application_id(client: TestClient) -> int:
    response = client.post("/applications", json=APPLICATION)
    assert response.status_code == 201, response.text
    return response.json()["id"]


@pytest.fixture
def analyzed(client: TestClient, db_sink: DatabaseLogSink, application_id: int) -> int:
    analyze(client, db_sink, application_id, KEYWORDS)
    return application_id


def put_base(client: TestClient, text_: str = BASE_RESUME) -> dict:
    response = client.put("/resume", json={"content_markdown": text_})
    assert response.status_code == 200, response.text
    return response.json()


def insert_resume(engine: Engine, application_id: int | None, markdown: str) -> int:
    with engine.begin() as conn:
        return conn.execute(
            text(
                "INSERT INTO resumes (application_id, content_markdown, status) "
                "VALUES (:application_id, :markdown, 'draft') RETURNING id"
            ),
            {"application_id": application_id, "markdown": markdown},
        ).scalar_one()


def count(engine: Engine, table: str) -> int:
    with engine.connect() as conn:
        return conn.execute(text(f"SELECT count(*) FROM {table}")).scalar_one()


# --- Without resume_id --------------------------------------------------------------------------


def test_get_returns_covered_missing_and_ratio_for_the_base_resume(
    client: TestClient, analyzed: int
) -> None:
    put_base(client)

    response = client.get(f"/applications/{analyzed}/coverage")

    assert response.status_code == 200
    assert response.json() == {
        "covered": ["ruby on rails", "postgresql"],
        "missing": ["ci/cd", "react"],
        "ratio": 0.5,
    }


def test_get_without_resume_id_has_no_comparison_fields(client: TestClient, analyzed: int) -> None:
    put_base(client)

    body = client.get(f"/applications/{analyzed}/coverage").json()

    assert set(body) == {"covered", "missing", "ratio"}


def test_get_follows_the_current_base_resume_text_every_time(
    client: TestClient, analyzed: int
) -> None:
    put_base(client)
    first = client.get(f"/applications/{analyzed}/coverage").json()

    put_base(client, "Ruby on Rails, PostgreSQL, CI/CD and React.")
    second = client.get(f"/applications/{analyzed}/coverage").json()

    assert first["ratio"] == 0.5
    assert second == {
        "covered": KEYWORDS,
        "missing": [],
        "ratio": 1.0,
    }


# --- With resume_id -----------------------------------------------------------------------------


def test_get_with_resume_id_adds_base_newly_covered_and_still_missing(
    client: TestClient, analyzed: int, test_engine: Engine
) -> None:
    put_base(client)
    tailored = insert_resume(test_engine, analyzed, "Ruby on Rails, CI/CD and React.")

    response = client.get(f"/applications/{analyzed}/coverage", params={"resume_id": tailored})

    assert response.status_code == 200
    assert response.json() == {
        "covered": ["ruby on rails", "ci/cd", "react"],
        "missing": ["postgresql"],
        "ratio": 0.75,
        "base": {
            "covered": ["ruby on rails", "postgresql"],
            "missing": ["ci/cd", "react"],
            "ratio": 0.5,
        },
        "newly_covered": ["ci/cd", "react"],
        "still_missing": [],
    }


def test_get_with_a_resume_of_another_application_is_404(
    client: TestClient, analyzed: int, test_engine: Engine
) -> None:
    put_base(client)
    other = client.post("/applications", json={**APPLICATION, "company": "Other Co"}).json()["id"]
    foreign = insert_resume(test_engine, other, "React")

    response = client.get(f"/applications/{analyzed}/coverage", params={"resume_id": foreign})

    assert response.status_code == 404
    assert response.json() == {"detail": "resume not found"}


def test_get_with_an_unknown_resume_id_is_404(client: TestClient, analyzed: int) -> None:
    put_base(client)

    response = client.get(f"/applications/{analyzed}/coverage", params={"resume_id": 999})

    assert response.status_code == 404
    assert response.json() == {"detail": "resume not found"}


def test_get_with_a_resume_id_that_is_not_a_number_is_422(
    client: TestClient, analyzed: int
) -> None:
    put_base(client)

    response = client.get(f"/applications/{analyzed}/coverage", params={"resume_id": "abc"})

    assert response.status_code == 422


# --- Errors -------------------------------------------------------------------------------------


def test_get_for_an_unknown_application_is_404(client: TestClient) -> None:
    put_base(client)

    response = client.get("/applications/999/coverage")

    assert response.status_code == 404
    assert response.json() == {"detail": "application not found"}


def test_get_without_an_analysis_is_404(client: TestClient, application_id: int) -> None:
    put_base(client)

    response = client.get(f"/applications/{application_id}/coverage")

    assert response.status_code == 404
    assert response.json() == {"detail": "analysis not found"}


def test_get_with_only_a_rejected_analysis_is_404(
    client: TestClient, db_sink: DatabaseLogSink, application_id: int
) -> None:
    put_base(client)
    rejected = analyze(client, db_sink, application_id, KEYWORDS)
    assert client.post(f"/analyses/{rejected['id']}/reject").status_code == 200

    response = client.get(f"/applications/{application_id}/coverage")

    assert response.status_code == 404
    assert response.json() == {"detail": "analysis not found"}


def test_get_without_a_base_resume_is_404(client: TestClient, analyzed: int) -> None:
    response = client.get(f"/applications/{analyzed}/coverage")

    assert response.status_code == 404
    assert response.json() == {"detail": "resume not found"}


# --- Which analysis -----------------------------------------------------------------------------


def test_get_uses_the_approved_analysis_even_when_a_newer_draft_exists(
    client: TestClient, db_sink: DatabaseLogSink, application_id: int
) -> None:
    put_base(client)
    approved = analyze(client, db_sink, application_id, ["postgresql"])
    assert client.post(f"/analyses/{approved['id']}/approve").status_code == 200
    analyze(client, db_sink, application_id, ["react", "aws"])

    body = client.get(f"/applications/{application_id}/coverage").json()

    assert body == {"covered": ["postgresql"], "missing": [], "ratio": 1.0}


def test_get_uses_the_latest_draft_when_none_is_approved(
    client: TestClient, db_sink: DatabaseLogSink, application_id: int
) -> None:
    put_base(client)
    analyze(client, db_sink, application_id, ["react"])
    analyze(client, db_sink, application_id, ["postgresql", "aws"])

    body = client.get(f"/applications/{application_id}/coverage").json()

    assert body["covered"] == ["postgresql"]
    assert body["missing"] == ["aws"]


# --- Never stored, and in /docs -----------------------------------------------------------------


def test_get_writes_nothing(client: TestClient, analyzed: int, test_engine: Engine) -> None:
    put_base(client)
    tables = ["applications", "posting_analyses", "resumes", "ai_calls", "timeline_events"]
    before = {table: count(test_engine, table) for table in tables}

    assert client.get(f"/applications/{analyzed}/coverage").status_code == 200

    assert {table: count(test_engine, table) for table in tables} == before


def test_the_endpoint_is_documented_in_openapi(client: TestClient) -> None:
    spec = client.get("/openapi.json").json()

    operation = spec["paths"]["/applications/{application_id}/coverage"]["get"]
    assert {parameter["name"] for parameter in operation["parameters"]} == {
        "application_id",
        "resume_id",
    }
    assert {"200", "404", "422"} <= set(operation["responses"])


def test_no_ats_score_wording_in_the_app() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent / "app"
    offenders = [
        str(path)
        for path in root.rglob("*.py")
        if "ats score" in path.read_text().lower().replace("_", " ")
    ]
    assert offenders == []
