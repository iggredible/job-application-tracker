"""`GET /metrics/pipeline` and `GET /metrics/ai` against a real database (feature 14).

One small dataset with known answers is built by hand. The clock is fixed, so "stale" and the
days in each stage are exact.

Seven applications (days are before the fixed "now"):

| Application | Timeline                                  | Stage      | Sent                      |
| ----------- | ----------------------------------------- | ---------- | ------------------------- |
| Alpha       | saved -30, applied -28, screening -20     | screening  | tailored                  |
| Beta        | saved -30, applied -25, rejected -10      | rejected   | tailored                  |
| Gamma       | saved -3, applied -2                      | applied    | snapshot of the base      |
| Delta       | saved -1                                  | saved      |                           |
| Eps         | saved -20, applied -19, withdrawn -5      | withdrawn  | tailored                  |
| Zeta        | saved -14                                 | saved      |                           |
| Theta       | saved -13                                 | saved      |                           |
"""

from datetime import timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    AICall,
    AIFeature,
    Application,
    EventType,
    Resume,
    ReviewStatus,
    Source,
    Stage,
    TimelineEvent,
)
from tests.conftest import FakeClock

S = Stage


def add_application(
    session: Session, clock: FakeClock, name: str, stage: Stage, steps: list[tuple[Stage, float]]
) -> Application:
    """An application whose timeline is `steps`: (stage entered, days before now)."""
    application = Application(
        company=name, role="Engineer", posting_text="posting", source=Source.OTHER, stage=stage
    )
    session.add(application)
    session.flush()
    previous: Stage | None = None
    for to_stage, days_ago in steps:
        session.add(
            TimelineEvent(
                application_id=application.id,
                type=EventType.STAGE_CHANGE,
                from_stage=previous,
                to_stage=to_stage,
                created_at=clock.now - timedelta(days=days_ago),
            )
        )
        previous = to_stage
    session.flush()
    return application


def add_tailored(
    session: Session, application: Application, *, model: str = "m", send: bool = True
) -> Resume:
    """An approved tailored resume with its AI call, sent with the application when `send`."""
    call = AICall(
        application_id=application.id,
        feature=AIFeature.TAILOR_RESUME,
        prompt_version="v1",
        model=model,
        request_json={},
        input_tokens=100,
        output_tokens=50,
        estimated_cost=Decimal("0.01"),
        latency_ms=1000,
        schema_valid=True,
    )
    session.add(call)
    session.flush()
    resume = Resume(
        application_id=application.id,
        ai_call_id=call.id,
        draft_markdown="# Draft",
        content_markdown="# Draft",
        status=ReviewStatus.APPROVED,
    )
    session.add(resume)
    session.flush()
    if send:
        application.submitted_resume_id = resume.id
    return resume


def add_snapshot(session: Session, application: Application) -> Resume:
    """A snapshot of the base resume: it belongs to an application and has no AI call."""
    snapshot = Resume(
        application_id=application.id,
        content_markdown="# Base",
        status=ReviewStatus.APPROVED,
    )
    session.add(snapshot)
    session.flush()
    application.submitted_resume_id = snapshot.id
    return snapshot


@pytest.fixture
def dataset(db_session: Session, clock: FakeClock) -> None:
    def make(name: str, stage: Stage, *steps: tuple[Stage, float]) -> Application:
        return add_application(db_session, clock, name, stage, list(steps))

    alpha = make("Alpha", S.SCREENING, (S.SAVED, 30), (S.APPLIED, 28), (S.SCREENING, 20))
    beta = make("Beta", S.REJECTED, (S.SAVED, 30), (S.APPLIED, 25), (S.REJECTED, 10))
    gamma = make("Gamma", S.APPLIED, (S.SAVED, 3), (S.APPLIED, 2))
    make("Delta", S.SAVED, (S.SAVED, 1))
    eps = make("Eps", S.WITHDRAWN, (S.SAVED, 20), (S.APPLIED, 19), (S.WITHDRAWN, 5))
    make("Zeta", S.SAVED, (S.SAVED, 14))
    make("Theta", S.SAVED, (S.SAVED, 13))
    add_tailored(db_session, alpha)
    add_tailored(db_session, beta)
    add_tailored(db_session, eps)
    add_snapshot(db_session, gamma)
    db_session.commit()


# --- pipeline -----------------------------------------------------------------------------------


def test_the_pipeline_numbers_match_the_hand_built_timeline(
    client: TestClient, dataset: None
) -> None:
    body = client.get("/metrics/pipeline").json()

    assert body["total_applications"] == 7
    assert body["applied_applications"] == 4
    assert body["funnel"] == [
        {"stage": "applied", "count": 4, "share_of_previous": None},
        {"stage": "screening", "count": 1, "share_of_previous": 0.25},
        {"stage": "interviewing", "count": 0, "share_of_previous": 0.0},
        {"stage": "offer", "count": 0, "share_of_previous": None},
    ]
    assert body["response"] == {"applied": 4, "responses": 2, "rate": 0.5}


def test_time_in_stage_counts_only_completed_intervals(client: TestClient, dataset: None) -> None:
    body = client.get("/metrics/pipeline").json()

    assert body["time_in_stage"] == [
        # Alpha 2 days, Beta 5, Gamma 1, Eps 1. Delta, Zeta and Theta are still in Saved.
        {"stage": "saved", "median_days": 1.5, "sample_size": 4},
        # Alpha 8, Beta 15, Eps 14. Gamma is still in Applied.
        {"stage": "applied", "median_days": 14.0, "sample_size": 3},
        {"stage": "screening", "median_days": None, "sample_size": 0},
        {"stage": "interviewing", "median_days": None, "sample_size": 0},
        {"stage": "offer", "median_days": None, "sample_size": 0},
    ]


def test_stale_applications_use_the_feature_3_rule(client: TestClient, dataset: None) -> None:
    # Alpha (20 days idle) and Zeta (exactly 14) are stale. Theta (13) is not, and Beta and Eps
    # are in terminal stages.
    assert client.get("/metrics/pipeline").json()["stale_applications"] == 2


def test_a_note_resets_the_stale_clock(
    client: TestClient, db_session: Session, clock: FakeClock
) -> None:
    # Saved 20 days ago, so stale, until a note two days ago counts as activity.
    quiet = add_application(db_session, clock, "Quiet", S.SAVED, [(S.SAVED, 20)])
    noted = add_application(db_session, clock, "Noted", S.SAVED, [(S.SAVED, 20)])
    db_session.add(
        TimelineEvent(
            application_id=noted.id,
            type=EventType.NOTE,
            note="Called the recruiter",
            created_at=clock.now - timedelta(days=2),
        )
    )
    db_session.commit()
    assert quiet.id != noted.id

    assert client.get("/metrics/pipeline").json()["stale_applications"] == 1


def test_an_applied_application_with_no_submitted_resume_is_in_neither_group(
    client: TestClient, db_session: Session, clock: FakeClock
) -> None:
    # It still counts as applied and as a response; it is only left out of tailored vs base.
    add_application(
        db_session, clock, "Unsent", S.REJECTED, [(S.SAVED, 9), (S.APPLIED, 8), (S.REJECTED, 4)]
    )
    db_session.commit()

    body = client.get("/metrics/pipeline").json()

    assert body["response"] == {"applied": 1, "responses": 1, "rate": 1.0}
    assert body["resume_comparison"] == {
        "tailored": {"applied": 0, "responses": 0, "rate": None},
        "base": {"applied": 0, "responses": 0, "rate": None},
    }


def test_a_snapshot_of_the_base_resume_counts_as_base(client: TestClient, dataset: None) -> None:
    body = client.get("/metrics/pipeline").json()

    # Tailored: Alpha and Beta responded, Eps did not. Base: Gamma (a snapshot), no response.
    assert body["resume_comparison"] == {
        "tailored": {"applied": 3, "responses": 2, "rate": pytest.approx(2 / 3)},
        "base": {"applied": 1, "responses": 0, "rate": 0.0},
    }


def test_reached_a_stage_is_read_from_the_timeline_not_the_current_stage(
    client: TestClient, db_session: Session, clock: FakeClock
) -> None:
    # The stage column says saved, the timeline says it got as far as Interviewing.
    add_application(
        db_session,
        clock,
        "Mismatch",
        S.SAVED,
        [(S.SAVED, 10), (S.APPLIED, 8), (S.SCREENING, 6), (S.INTERVIEWING, 4)],
    )
    db_session.commit()

    body = client.get("/metrics/pipeline").json()

    assert [step["count"] for step in body["funnel"]] == [1, 1, 1, 0]
    assert body["applied_applications"] == 1


def test_an_empty_database_gives_zeros_and_nulls(client: TestClient) -> None:
    pipeline = client.get("/metrics/pipeline")
    ai = client.get("/metrics/ai")

    assert pipeline.status_code == 200
    body = pipeline.json()
    assert (body["total_applications"], body["applied_applications"]) == (0, 0)
    assert [step["count"] for step in body["funnel"]] == [0, 0, 0, 0]
    assert all(row["median_days"] is None for row in body["time_in_stage"])
    assert body["response"] == {"applied": 0, "responses": 0, "rate": None}
    assert body["stale_applications"] == 0
    assert body["resume_comparison"] == {
        "tailored": {"applied": 0, "responses": 0, "rate": None},
        "base": {"applied": 0, "responses": 0, "rate": None},
    }
    assert ai.status_code == 200
    assert ai.json() == {"rows": []}


# --- AI -----------------------------------------------------------------------------------------


def test_the_ai_row_counts_the_tailored_resumes_and_not_the_snapshot(
    client: TestClient, dataset: None
) -> None:
    body = client.get("/metrics/ai").json()

    # Three tailored resumes, each approved as is. Gamma's approved snapshot is not one of them.
    assert body["rows"] == [
        {
            "feature": "tailor_resume",
            "prompt_version": "v1",
            "model": "m",
            "calls": 3,
            "failed_calls": 0,
            "approved_as_is": 3,
            "edited_then_approved": 0,
            "rejected": 0,
            "pending": 0,
            "superseded": 0,
            "avg_edit_ratio": 0.0,
            "avg_flags_per_draft": 0.0,
            "input_tokens": 300,
            "output_tokens": 150,
            "estimated_cost": pytest.approx(0.03),
            "median_latency_ms": 1000.0,
        }
    ]


def test_seeded_rows_stay_separate_from_real_calls(
    client: TestClient, db_session: Session, clock: FakeClock
) -> None:
    real = add_application(db_session, clock, "Real", S.SAVED, [(S.SAVED, 1)])
    seeded = add_application(db_session, clock, "Seeded", S.SAVED, [(S.SAVED, 1)])
    add_tailored(db_session, real, model="claude", send=False)
    add_tailored(db_session, seeded, model="seed", send=False)
    db_session.commit()

    rows = client.get("/metrics/ai").json()["rows"]

    assert [(row["model"], row["calls"]) for row in rows] == [("claude", 1), ("seed", 1)]


def test_a_failed_call_is_counted_and_has_no_outcome(
    client: TestClient, db_session: Session, clock: FakeClock
) -> None:
    application = add_application(db_session, clock, "A", S.SAVED, [(S.SAVED, 1)])
    db_session.add(
        AICall(
            application_id=application.id,
            feature=AIFeature.POSTING_ANALYSIS,
            prompt_version="v1",
            model="m",
            request_json={},
            latency_ms=500,
            schema_valid=False,
            error="api_error: boom",
        )
    )
    db_session.commit()

    (row,) = client.get("/metrics/ai").json()["rows"]

    assert (row["calls"], row["failed_calls"]) == (1, 1)
    assert (row["approved_as_is"], row["rejected"], row["pending"], row["superseded"]) == (
        0,
        0,
        0,
        0,
    )
    assert row["edited_then_approved"] is None  # a posting analysis has no edit step
    assert row["avg_edit_ratio"] is None
    assert row["avg_flags_per_draft"] is None


# --- read-only, and in /docs --------------------------------------------------------------------


def test_the_metrics_endpoints_never_write(
    client: TestClient, dataset: None, db_session: Session
) -> None:
    tables = (AICall, TimelineEvent, Resume, Application)
    before = [db_session.scalar(select(func.count()).select_from(t)) for t in tables]

    assert client.get("/metrics/pipeline").status_code == 200
    assert client.get("/metrics/ai").status_code == 200

    db_session.expire_all()
    assert [db_session.scalar(select(func.count()).select_from(t)) for t in tables] == before
    # And there is no other way in: both routes answer GET only.
    paths = client.get("/openapi.json").json()["paths"]
    metrics = {path: set(item) for path, item in paths.items() if path.startswith("/metrics")}
    assert metrics == {"/metrics/pipeline": {"get"}, "/metrics/ai": {"get"}}


def test_the_response_schemas_appear_in_the_api_docs(client: TestClient) -> None:
    spec = client.get("/openapi.json").json()

    for path, schema in (("/metrics/pipeline", "PipelineMetrics"), ("/metrics/ai", "AIMetrics")):
        ok = spec["paths"][path]["get"]["responses"]["200"]["content"]["application/json"]
        assert ok["schema"]["$ref"].endswith(f"/{schema}")
        assert schema in spec["components"]["schemas"]
    assert {"FunnelStep", "StageDuration", "AIMetricsRow"} <= set(spec["components"]["schemas"])
