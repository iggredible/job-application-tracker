"""The tailored resume endpoints: the guards, what is saved, the lock and the list."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.ai.schemas import (
    Experience,
    PostingAnalysisOutput,
    Requirement,
    RequirementCategory,
    TailoredResume,
)
from app.ai.sinks import DatabaseLogSink
from app.ai.types import AIAPIError, AIConfigurationError, AIError
from app.api.ai import get_ai_client
from app.main import app
from app.models import AIFeature
from app.repositories.locks import GenerationLockRepository
from app.services.rendering import render_tailored_markdown
from tests.conftest import FakeClock
from tests.fakes import FakeAIClient

APPLICATION = {
    "company": "Northwind Freight",
    "role": "Senior Backend Engineer",
    "source": "linkedin",
    "posting_text": "Build services that book, track and settle every load.",
}

BASE = "# Jordan Avery\n\n## Summary\nOld summary.\n\n## Skills\nRuby on Rails, PostgreSQL\n"

TAILORED = TailoredResume(
    summary="Backend lead on Ruby on Rails.",
    experiences=[
        Experience(
            employer="Coldline Logistics",
            title="Lead Software Engineer",
            dates="Jun 2021 — May 2026",
            bullets=["Led a team of 5"],
        )
    ],
    skills=["Ruby on Rails", "PostgreSQL"],
)


def use_ai(fake: FakeAIClient) -> None:
    app.dependency_overrides[get_ai_client] = lambda: fake


def count(engine: Engine, table: str, where: str = "true") -> int:
    with engine.connect() as conn:
        return conn.execute(text(f"SELECT count(*) FROM {table} WHERE {where}")).scalar_one()


@pytest.fixture
def application_id(client: TestClient) -> int:
    response = client.post("/applications", json=APPLICATION)
    assert response.status_code == 201, response.text
    return response.json()["id"]


def make_analysis(
    client: TestClient,
    sink: DatabaseLogSink,
    application_id: int,
    *,
    keywords: list[str],
    decision: str | None,
) -> int:
    """An analysis with these keywords, then approved or rejected (or left as a draft)."""
    output = PostingAnalysisOutput(
        requirements=[Requirement(text="Rails", category=RequirementCategory.MUST_HAVE)],
        keywords=keywords,
    )
    use_ai(FakeAIClient(sink, output=output))
    response = client.post(f"/applications/{application_id}/analysis")
    assert response.status_code == 201, response.text
    analysis_id = response.json()["id"]
    if decision:
        assert client.post(f"/analyses/{analysis_id}/{decision}").status_code == 200
    return analysis_id


def save_base(client: TestClient) -> None:
    assert client.put("/resume", json={"content_markdown": BASE}).status_code == 200


@pytest.fixture
def ready(client: TestClient, db_sink: DatabaseLogSink, application_id: int) -> FakeAIClient:
    """An application with an approved analysis and a base resume, and a tailoring fake."""
    make_analysis(
        client,
        db_sink,
        application_id,
        keywords=["ruby on rails", "postgresql"],
        decision="approve",
    )
    save_base(client)
    fake = FakeAIClient(db_sink, output=TAILORED)
    use_ai(fake)
    return fake


@pytest.fixture
def other_session(test_engine: Engine) -> Iterator[Session]:
    with sessionmaker(bind=test_engine)() as session:
        yield session
        session.rollback()


def tailor(client: TestClient, application_id: int) -> dict:
    response = client.post(f"/applications/{application_id}/tailored-resumes")
    assert response.status_code == 201, response.text
    return response.json()


# --- POST: what is saved ------------------------------------------------------------------------


def test_post_makes_one_ai_call_and_saves_a_draft(
    client: TestClient, ready: FakeAIClient, application_id: int
) -> None:
    response = client.post(f"/applications/{application_id}/tailored-resumes")

    assert response.status_code == 201
    body = response.json()
    assert body["application_id"] == application_id
    assert body["status"] == "draft"
    assert body["prompt_version"] == "v1"
    assert body["created_at"]
    assert body["content_markdown"] == render_tailored_markdown(BASE, TAILORED)
    assert len(ready.calls) == 1
    assert ready.calls[0]["feature"] is AIFeature.TAILOR_RESUME


def test_post_saves_the_json_both_markdowns_the_status_and_the_ai_call_id(
    client: TestClient, ready: FakeAIClient, application_id: int, test_engine: Engine
) -> None:
    tailor(client, application_id)

    with test_engine.connect() as conn:
        resume = conn.execute(
            text(
                "SELECT application_id, ai_call_id, content_json, draft_markdown, "
                "content_markdown, status FROM resumes WHERE application_id IS NOT NULL"
            )
        ).one()
        call = conn.execute(
            text(
                "SELECT id, application_id, prompt_version, schema_valid FROM ai_calls "
                "WHERE feature = 'tailor_resume'"
            )
        ).one()
    expected = render_tailored_markdown(BASE, TAILORED)
    assert resume.application_id == application_id
    assert resume.ai_call_id == call.id
    assert resume.content_json == TAILORED.model_dump(mode="json")
    assert resume.draft_markdown == resume.content_markdown == expected
    assert resume.status == "draft"
    assert (call.application_id, call.prompt_version, call.schema_valid) == (
        application_id,
        "v1",
        True,
    )


def test_post_sends_the_base_resume_the_posting_and_the_approved_keywords(
    client: TestClient, ready: FakeAIClient, application_id: int
) -> None:
    tailor(client, application_id)

    user = ready.calls[0]["prompt"].user
    assert f"<base_resume>\n{BASE}\n</base_resume>" in user
    assert APPLICATION["posting_text"] in user
    assert "- ruby on rails\n- postgresql" in user
    assert "<examples>\n</examples>" in user  # no retrieval yet: tailoring works with none


def test_post_again_adds_a_draft_and_leaves_the_older_one_unchanged(
    client: TestClient,
    ready: FakeAIClient,
    application_id: int,
    clock: FakeClock,
    test_engine: Engine,
) -> None:
    first = tailor(client, application_id)
    clock.advance(hours=1)
    second = tailor(client, application_id)

    assert first["id"] != second["id"]
    with test_engine.connect() as conn:
        rows = conn.execute(
            text("SELECT id, ai_call_id, status FROM resumes WHERE application_id IS NOT NULL")
        ).all()
    assert len(rows) == 2
    assert {row.status for row in rows} == {"draft"}  # a new draft never changes an older one
    assert len({row.ai_call_id for row in rows}) == 2  # one AI call per resume
    assert count(test_engine, "ai_calls", "feature = 'tailor_resume'") == 2


# --- POST: the guards ---------------------------------------------------------------------------


def test_post_without_any_analysis_is_409_with_the_reason_and_calls_no_ai(
    client: TestClient, db_sink: DatabaseLogSink, application_id: int, test_engine: Engine
) -> None:
    save_base(client)
    fake = FakeAIClient(db_sink, output=TAILORED)
    use_ai(fake)

    response = client.post(f"/applications/{application_id}/tailored-resumes")

    assert response.status_code == 409
    assert response.json() == {"detail": "The posting analysis must be approved before tailoring."}
    assert fake.calls == []
    assert count(test_engine, "ai_calls") == 0
    assert count(test_engine, "resumes", "application_id IS NOT NULL") == 0


@pytest.mark.parametrize("decision", [None, "reject"])
def test_post_with_only_a_draft_or_rejected_analysis_is_409(
    client: TestClient, db_sink: DatabaseLogSink, application_id: int, decision: str | None
) -> None:
    make_analysis(client, db_sink, application_id, keywords=["go"], decision=decision)
    save_base(client)
    fake = FakeAIClient(db_sink, output=TAILORED)
    use_ai(fake)

    response = client.post(f"/applications/{application_id}/tailored-resumes")

    assert response.status_code == 409
    assert "approved" in response.json()["detail"]
    assert fake.calls == []


def test_post_uses_the_latest_approved_analysis_even_when_a_newer_draft_exists(
    client: TestClient, db_sink: DatabaseLogSink, application_id: int, clock: FakeClock
) -> None:
    make_analysis(client, db_sink, application_id, keywords=["go", "kafka"], decision="approve")
    clock.advance(hours=1)
    make_analysis(client, db_sink, application_id, keywords=["react"], decision=None)
    save_base(client)
    fake = FakeAIClient(db_sink, output=TAILORED)
    use_ai(fake)

    tailor(client, application_id)

    user = fake.calls[0]["prompt"].user
    assert "- go\n- kafka" in user
    assert "react" not in user


def test_post_without_a_base_resume_is_409_with_the_reason_and_calls_no_ai(
    client: TestClient, db_sink: DatabaseLogSink, application_id: int, test_engine: Engine
) -> None:
    make_analysis(client, db_sink, application_id, keywords=["go"], decision="approve")
    fake = FakeAIClient(db_sink, output=TAILORED)
    use_ai(fake)
    calls_before = count(test_engine, "ai_calls")

    response = client.post(f"/applications/{application_id}/tailored-resumes")

    assert response.status_code == 409
    assert response.json() == {"detail": "Save a base resume before tailoring."}
    assert fake.calls == []
    assert count(test_engine, "ai_calls") == calls_before


def test_post_for_an_unknown_application_is_404_and_calls_no_ai(
    client: TestClient, db_sink: DatabaseLogSink
) -> None:
    fake = FakeAIClient(db_sink, output=TAILORED)
    use_ai(fake)

    assert client.post("/applications/999/tailored-resumes").status_code == 404
    assert fake.calls == []


# --- POST: the lock and failures ----------------------------------------------------------------


def test_post_while_one_is_running_is_409(
    client: TestClient,
    ready: FakeAIClient,
    application_id: int,
    other_session: Session,
    test_engine: Engine,
) -> None:
    GenerationLockRepository(other_session).try_lock(AIFeature.TAILOR_RESUME, application_id)

    response = client.post(f"/applications/{application_id}/tailored-resumes")

    assert response.status_code == 409
    assert ready.calls == []
    assert count(test_engine, "resumes", "application_id IS NOT NULL") == 0

    other_session.rollback()  # the first request finishes
    assert client.post(f"/applications/{application_id}/tailored-resumes").status_code == 201


def test_an_analysis_running_does_not_block_tailoring(
    client: TestClient, ready: FakeAIClient, application_id: int, other_session: Session
) -> None:
    GenerationLockRepository(other_session).try_lock(AIFeature.POSTING_ANALYSIS, application_id)

    assert client.post(f"/applications/{application_id}/tailored-resumes").status_code == 201


@pytest.mark.parametrize("error", [AIAPIError, AIError])
def test_post_when_the_call_fails_is_502_with_the_failure_logged_and_nothing_saved(
    client: TestClient,
    ready: FakeAIClient,
    db_sink: DatabaseLogSink,
    application_id: int,
    test_engine: Engine,
    error: type[AIError],
) -> None:
    use_ai(FakeAIClient(db_sink, error=error))

    response = client.post(f"/applications/{application_id}/tailored-resumes")

    assert response.status_code == 502
    assert response.json() == {"detail": "The tailoring failed. Try again."}
    assert count(test_engine, "resumes", "application_id IS NOT NULL") == 0
    with test_engine.connect() as conn:
        assert (
            conn.execute(
                text("SELECT schema_valid FROM ai_calls WHERE feature = 'tailor_resume'")
            ).scalar_one()
            is False
        )


def test_a_failed_call_does_not_leave_the_lock_held(
    client: TestClient, ready: FakeAIClient, db_sink: DatabaseLogSink, application_id: int
) -> None:
    use_ai(FakeAIClient(db_sink, error=AIAPIError))
    assert client.post(f"/applications/{application_id}/tailored-resumes").status_code == 502

    use_ai(ready)

    assert client.post(f"/applications/{application_id}/tailored-resumes").status_code == 201


def test_post_without_an_api_key_is_503(
    client: TestClient, ready: FakeAIClient, application_id: int
) -> None:
    def not_configured() -> None:
        raise AIConfigurationError("ANTHROPIC_API_KEY is not set")

    app.dependency_overrides[get_ai_client] = not_configured

    response = client.post(f"/applications/{application_id}/tailored-resumes")

    assert response.status_code == 503
    assert "API_KEY" not in response.text


# --- GET ----------------------------------------------------------------------------------------


def test_get_with_no_drafts_is_an_empty_list_and_needs_no_ai_client(
    client: TestClient, application_id: int
) -> None:
    response = client.get(f"/applications/{application_id}/tailored-resumes")

    assert response.status_code == 200
    assert response.json() == []


def test_get_for_an_unknown_application_is_404(client: TestClient) -> None:
    assert client.get("/applications/999/tailored-resumes").status_code == 404


def test_get_lists_the_drafts_newest_first_with_status_prompt_version_and_date(
    client: TestClient, ready: FakeAIClient, application_id: int, clock: FakeClock
) -> None:
    first = tailor(client, application_id)
    clock.advance(hours=1)
    second = tailor(client, application_id)

    response = client.get(f"/applications/{application_id}/tailored-resumes")

    assert response.status_code == 200
    # `outcome` and `displayed` describe the whole list, so the older draft changed since its POST.
    derived = {"outcome", "displayed"}
    stable = [{k: v for k, v in r.items() if k not in derived} for r in response.json()]
    assert stable == [{k: v for k, v in r.items() if k not in derived} for r in (second, first)]
    assert [(r["status"], r["prompt_version"]) for r in response.json()] == [("draft", "v1")] * 2
    assert response.json()[0]["created_at"] > response.json()[1]["created_at"]


def test_get_does_not_list_a_base_resume_snapshot(
    client: TestClient, application_id: int, test_engine: Engine
) -> None:
    # A snapshot is a resume of this application that no AI call made (feature 11).
    with test_engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO resumes (application_id, content_markdown, status) "
                "VALUES (:application_id, 'snapshot of the base', 'approved')"
            ),
            {"application_id": application_id},
        )

    assert client.get(f"/applications/{application_id}/tailored-resumes").json() == []


def test_get_does_not_list_the_base_resume_or_another_applications_drafts(
    client: TestClient, ready: FakeAIClient, application_id: int
) -> None:
    other = client.post("/applications", json=APPLICATION).json()["id"]
    tailor(client, application_id)

    assert len(client.get(f"/applications/{application_id}/tailored-resumes").json()) == 1
    assert client.get(f"/applications/{other}/tailored-resumes").json() == []


# --- guardrail flags ----------------------------------------------------------------------------

# Everything TAILORED claims that BASE does not support: the employer, the title, the dates (2021
# and 2026 are not in BASE) and the number 5. The skills and keywords are in BASE.
DIRTY_FIELDS = ["employer", "title", "dates", "number"]

CLEAN_BASE = (
    "# Jordan Avery\n\n## Summary\nOld summary.\n\n## Experience\n"
    "### Lead Software Engineer — Coldline Logistics (Jun 2021 — May 2026)\n"
    "- Led a team of 5\n\n## Skills\nRuby on Rails, PostgreSQL\n"
)


def stored_flags(engine: Engine) -> list[dict]:
    with engine.connect() as conn:
        return conn.execute(
            text("SELECT guardrail_flags FROM resumes WHERE application_id IS NOT NULL")
        ).scalar_one()


def test_post_returns_a_flag_for_each_fact_that_is_not_in_the_base_resume(
    client: TestClient, ready: FakeAIClient, application_id: int
) -> None:
    body = tailor(client, application_id)

    assert [flag["field"] for flag in body["guardrail_flags"]] == DIRTY_FIELDS
    assert body["guardrail_flags"][0] == {
        "field": "employer",
        "value": "Coldline Logistics",
        "message": 'Employer "Coldline Logistics"',
    }
    assert body["guardrail_flags"][3]["message"] == 'Number "5" in "Led a team of 5"'


def test_post_stores_the_flags_as_generated(
    client: TestClient, ready: FakeAIClient, application_id: int, test_engine: Engine
) -> None:
    body = tailor(client, application_id)

    assert stored_flags(test_engine) == body["guardrail_flags"]


def test_a_draft_with_nothing_to_flag_has_no_flags_returned_or_stored(
    client: TestClient, ready: FakeAIClient, application_id: int, test_engine: Engine
) -> None:
    assert client.put("/resume", json={"content_markdown": CLEAN_BASE}).status_code == 200

    body = tailor(client, application_id)

    assert body["guardrail_flags"] == []
    assert stored_flags(test_engine) == []


def test_flags_do_not_block_the_draft_and_do_not_change_it(
    client: TestClient, ready: FakeAIClient, application_id: int, test_engine: Engine
) -> None:
    body = tailor(client, application_id)

    assert body["status"] == "draft"
    assert body["content_markdown"] == render_tailored_markdown(BASE, TAILORED)  # not auto-fixed


def test_get_returns_the_current_flags_of_each_draft(
    client: TestClient, ready: FakeAIClient, application_id: int, clock: FakeClock
) -> None:
    tailor(client, application_id)
    clock.advance(hours=1)
    tailor(client, application_id)

    drafts = client.get(f"/applications/{application_id}/tailored-resumes").json()

    assert len(drafts) == 2
    for draft in drafts:
        assert [flag["field"] for flag in draft["guardrail_flags"]] == DIRTY_FIELDS


def test_get_follows_an_edit_while_the_stored_flags_stay_as_generated(
    client: TestClient, ready: FakeAIClient, application_id: int, test_engine: Engine
) -> None:
    tailor(client, application_id)
    with test_engine.begin() as conn:
        # What saving an edit will do (feature 10): content_markdown changes, draft_markdown not.
        conn.execute(
            text(
                "UPDATE resumes SET content_markdown = replace(content_markdown, "
                "'Led a team of 5', 'Led a team') WHERE application_id IS NOT NULL"
            )
        )

    [draft] = client.get(f"/applications/{application_id}/tailored-resumes").json()

    assert [flag["field"] for flag in draft["guardrail_flags"]] == ["employer", "title", "dates"]
    assert [flag["field"] for flag in stored_flags(test_engine)] == DIRTY_FIELDS
