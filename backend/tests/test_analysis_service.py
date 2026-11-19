"""PostingAnalysisService: run, display rule, review and the per-application lock."""

import threading
from collections.abc import Iterator

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.ai.schemas import PostingAnalysisOutput, Requirement, RequirementCategory
from app.ai.sinks import DatabaseLogSink
from app.ai.types import AIAPIError, AIRefusalError
from app.models import AIFeature, ReviewStatus
from app.repositories.applications import ApplicationRepository
from app.repositories.locks import GenerationLockRepository
from app.repositories.posting_analyses import PostingAnalysisRepository
from app.repositories.timeline import TimelineRepository
from app.schemas.application import ApplicationCreate
from app.services.analysis import (
    AnalysisInProgress,
    AnalysisNotFound,
    PostingAnalysisService,
)
from app.services.applications import ApplicationNotFound, ApplicationService
from app.services.review import NotReviewable, apply_decision
from tests.conftest import FakeClock
from tests.fakes import FakeAIClient

OUTPUT = PostingAnalysisOutput(
    requirements=[
        Requirement(text="Ruby on Rails in production", category=RequirementCategory.MUST_HAVE),
        Requirement(text="React", category=RequirementCategory.NICE_TO_HAVE),
    ],
    keywords=["Ruby on Rails", "PostgreSQL", "react"],
)


def make_service(session: Session, clock: FakeClock) -> PostingAnalysisService:
    return PostingAnalysisService(
        PostingAnalysisRepository(session),
        ApplicationRepository(session),
        GenerationLockRepository(session),
        clock,
    )


def make_application(session: Session) -> int:
    service = ApplicationService(ApplicationRepository(session), TimelineRepository(session))
    created = service.create(
        ApplicationCreate(
            company="Northwind Freight",
            role="Senior Backend Engineer",
            source="linkedin",
            posting_text="Build services.",
        )
    )
    return created.application.id


def count(engine: Engine, table: str) -> int:
    with engine.connect() as conn:
        return conn.execute(text(f"SELECT count(*) FROM {table}")).scalar_one()


@pytest.fixture
def fake_ai(db_sink: DatabaseLogSink) -> FakeAIClient:
    return FakeAIClient(db_sink, output=OUTPUT)


@pytest.fixture
def other_session(test_engine: Engine) -> Iterator[Session]:
    """A second connection, standing in for a parallel request."""
    with sessionmaker(bind=test_engine)() as session:
        yield session
        session.rollback()


# --- run ----------------------------------------------------------------------------------------


def test_run_saves_the_result_as_a_draft_linked_to_its_ai_call(
    db_session: Session, clock: FakeClock, fake_ai: FakeAIClient, test_engine: Engine
) -> None:
    application_id = make_application(db_session)

    view = make_service(db_session, clock).run(application_id, fake_ai)

    analysis = view.analysis
    assert analysis.status is ReviewStatus.DRAFT
    assert analysis.application_id == application_id
    assert analysis.created_at == clock.now
    assert analysis.reviewed_at is None
    assert view.prompt_version == "v1"
    assert count(test_engine, "ai_calls") == 1
    with test_engine.connect() as conn:
        call_id = conn.execute(text("SELECT id FROM ai_calls")).scalar_one()
    assert analysis.ai_call_id == call_id


def test_run_saves_the_requirements_and_the_trimmed_keywords(
    db_session: Session, clock: FakeClock, fake_ai: FakeAIClient
) -> None:
    application_id = make_application(db_session)

    analysis = make_service(db_session, clock).run(application_id, fake_ai).analysis

    assert analysis.requirements == [
        {"text": "Ruby on Rails in production", "category": "must_have"},
        {"text": "React", "category": "nice_to_have"},
    ]
    assert analysis.keywords == ["ruby on rails", "postgresql", "react"]


def test_run_makes_exactly_one_ai_call_with_the_posting_text(
    db_session: Session, clock: FakeClock, fake_ai: FakeAIClient
) -> None:
    application_id = make_application(db_session)

    make_service(db_session, clock).run(application_id, fake_ai)

    assert len(fake_ai.calls) == 1
    assert fake_ai.calls[0]["feature"] is AIFeature.POSTING_ANALYSIS
    assert "Build services." in fake_ai.calls[0]["prompt"].user


def test_running_again_creates_a_new_row_and_keeps_the_old_one(
    db_session: Session, clock: FakeClock, fake_ai: FakeAIClient, test_engine: Engine
) -> None:
    application_id = make_application(db_session)
    service = make_service(db_session, clock)

    first = service.run(application_id, fake_ai).analysis
    clock.advance(hours=1)
    second = service.run(application_id, fake_ai).analysis

    assert first.id != second.id
    assert count(test_engine, "posting_analyses") == 2
    assert first.status is ReviewStatus.DRAFT  # an older draft is never auto-rejected


def test_run_for_an_unknown_application_raises_not_found_and_calls_no_ai(
    db_session: Session, clock: FakeClock, fake_ai: FakeAIClient
) -> None:
    with pytest.raises(ApplicationNotFound):
        make_service(db_session, clock).run(999, fake_ai)

    assert fake_ai.calls == []


@pytest.mark.parametrize("error", [AIAPIError, AIRefusalError])
def test_a_failed_call_saves_no_analysis_but_keeps_the_log_row(
    db_session: Session,
    clock: FakeClock,
    db_sink: DatabaseLogSink,
    test_engine: Engine,
    error: type,
) -> None:
    application_id = make_application(db_session)
    failing = FakeAIClient(db_sink, error=error)

    with pytest.raises(error):
        make_service(db_session, clock).run(application_id, failing)

    assert count(test_engine, "posting_analyses") == 0
    assert count(test_engine, "ai_calls") == 1
    with test_engine.connect() as conn:
        assert conn.execute(text("SELECT schema_valid FROM ai_calls")).scalar_one() is False


# --- the lock -----------------------------------------------------------------------------------


def test_a_second_run_while_one_is_in_flight_is_refused_before_any_ai_call(
    db_session: Session,
    clock: FakeClock,
    fake_ai: FakeAIClient,
    other_session: Session,
    test_engine: Engine,
) -> None:
    application_id = make_application(db_session)
    assert GenerationLockRepository(other_session).try_lock(
        AIFeature.POSTING_ANALYSIS, application_id
    )

    with pytest.raises(AnalysisInProgress):
        make_service(db_session, clock).run(application_id, fake_ai)

    assert fake_ai.calls == []
    assert count(test_engine, "ai_calls") == 0


def test_the_lock_is_per_application_and_per_feature(
    db_session: Session, other_session: Session
) -> None:
    holder = GenerationLockRepository(other_session)
    assert holder.try_lock(AIFeature.POSTING_ANALYSIS, 1)

    contender = GenerationLockRepository(db_session)

    assert not contender.try_lock(AIFeature.POSTING_ANALYSIS, 1)
    assert contender.try_lock(AIFeature.POSTING_ANALYSIS, 2)
    assert contender.try_lock(AIFeature.TAILOR_RESUME, 1)


def test_the_lock_is_released_after_a_successful_run(
    db_session: Session, clock: FakeClock, fake_ai: FakeAIClient, other_session: Session
) -> None:
    application_id = make_application(db_session)
    make_service(db_session, clock).run(application_id, fake_ai)

    assert GenerationLockRepository(other_session).try_lock(
        AIFeature.POSTING_ANALYSIS, application_id
    )


def test_the_lock_is_released_after_a_failed_run(
    db_session: Session, clock: FakeClock, db_sink: DatabaseLogSink, other_session: Session
) -> None:
    application_id = make_application(db_session)
    with pytest.raises(AIAPIError):
        make_service(db_session, clock).run(application_id, FakeAIClient(db_sink, error=AIAPIError))

    assert GenerationLockRepository(other_session).try_lock(
        AIFeature.POSTING_ANALYSIS, application_id
    )


# --- which analysis the card shows --------------------------------------------------------------


def test_nothing_to_display_before_the_first_run(db_session: Session, clock: FakeClock) -> None:
    application_id = make_application(db_session)

    assert make_service(db_session, clock).get_for_display(application_id) is None


def test_display_for_an_unknown_application_raises_not_found(
    db_session: Session, clock: FakeClock
) -> None:
    with pytest.raises(ApplicationNotFound):
        make_service(db_session, clock).get_for_display(999)


def test_the_most_recent_analysis_is_displayed(
    db_session: Session, clock: FakeClock, fake_ai: FakeAIClient
) -> None:
    application_id = make_application(db_session)
    service = make_service(db_session, clock)
    service.run(application_id, fake_ai)
    clock.advance(hours=1)
    newest = service.run(application_id, fake_ai).analysis

    shown = service.get_for_display(application_id)

    assert shown is not None
    assert shown.analysis.id == newest.id
    assert shown.prompt_version == "v1"


def test_ties_on_the_clock_are_broken_by_id(
    db_session: Session, clock: FakeClock, fake_ai: FakeAIClient
) -> None:
    application_id = make_application(db_session)
    service = make_service(db_session, clock)
    service.run(application_id, fake_ai)
    newest = service.run(application_id, fake_ai).analysis  # same clock time

    shown = service.get_for_display(application_id)

    assert shown is not None and shown.analysis.id == newest.id


def test_a_rejected_newest_does_not_hide_an_older_approved_one(
    db_session: Session, clock: FakeClock, fake_ai: FakeAIClient
) -> None:
    application_id = make_application(db_session)
    service = make_service(db_session, clock)
    approved = service.run(application_id, fake_ai).analysis
    service.approve(approved.id)
    clock.advance(hours=1)
    rejected = service.run(application_id, fake_ai).analysis
    service.reject(rejected.id)

    shown = service.get_for_display(application_id)

    assert shown is not None
    assert shown.analysis.id == approved.id
    assert shown.analysis.status is ReviewStatus.APPROVED


def test_a_rejected_newest_is_shown_when_nothing_is_approved(
    db_session: Session, clock: FakeClock, fake_ai: FakeAIClient
) -> None:
    application_id = make_application(db_session)
    service = make_service(db_session, clock)
    service.run(application_id, fake_ai)  # an older draft
    clock.advance(hours=1)
    rejected = service.run(application_id, fake_ai).analysis
    service.reject(rejected.id)

    shown = service.get_for_display(application_id)

    assert shown is not None
    assert shown.analysis.id == rejected.id
    assert shown.analysis.status is ReviewStatus.REJECTED


def test_a_newer_draft_is_shown_over_an_older_approved_one(
    db_session: Session, clock: FakeClock, fake_ai: FakeAIClient
) -> None:
    application_id = make_application(db_session)
    service = make_service(db_session, clock)
    approved = service.run(application_id, fake_ai).analysis
    service.approve(approved.id)
    clock.advance(hours=1)
    draft = service.run(application_id, fake_ai).analysis

    shown = service.get_for_display(application_id)

    assert shown is not None
    assert shown.analysis.id == draft.id
    assert shown.analysis.status is ReviewStatus.DRAFT


def test_the_latest_approved_one_wins_when_a_rejected_newest_follows_two_approved(
    db_session: Session, clock: FakeClock, fake_ai: FakeAIClient
) -> None:
    application_id = make_application(db_session)
    service = make_service(db_session, clock)
    first = service.run(application_id, fake_ai).analysis
    service.approve(first.id)
    clock.advance(hours=1)
    second = service.run(application_id, fake_ai).analysis
    service.approve(second.id)
    clock.advance(hours=1)
    third = service.run(application_id, fake_ai).analysis
    service.reject(third.id)

    shown = service.get_for_display(application_id)

    assert shown is not None and shown.analysis.id == second.id


# --- approve and reject -------------------------------------------------------------------------


def test_approve_sets_the_status_and_the_review_time(
    db_session: Session, clock: FakeClock, fake_ai: FakeAIClient
) -> None:
    application_id = make_application(db_session)
    service = make_service(db_session, clock)
    analysis = service.run(application_id, fake_ai).analysis
    clock.advance(hours=2)

    approved = service.approve(analysis.id)

    assert approved.analysis.status is ReviewStatus.APPROVED
    assert approved.analysis.reviewed_at == clock.now
    assert approved.prompt_version == "v1"


def test_reject_sets_the_status_and_the_review_time(
    db_session: Session, clock: FakeClock, fake_ai: FakeAIClient
) -> None:
    application_id = make_application(db_session)
    service = make_service(db_session, clock)
    analysis = service.run(application_id, fake_ai).analysis
    clock.advance(hours=2)

    rejected = service.reject(analysis.id)

    assert rejected.analysis.status is ReviewStatus.REJECTED
    assert rejected.analysis.reviewed_at == clock.now


def test_a_decision_is_saved(
    db_session: Session, clock: FakeClock, fake_ai: FakeAIClient, test_engine: Engine
) -> None:
    application_id = make_application(db_session)
    service = make_service(db_session, clock)
    analysis = service.run(application_id, fake_ai).analysis

    service.approve(analysis.id)

    with test_engine.connect() as conn:
        row = conn.execute(text("SELECT status, reviewed_at FROM posting_analyses")).one()
    assert row.status == "approved"
    assert row.reviewed_at == clock.now


def test_a_decided_analysis_cannot_be_decided_again(
    db_session: Session, clock: FakeClock, fake_ai: FakeAIClient
) -> None:
    application_id = make_application(db_session)
    service = make_service(db_session, clock)
    analysis = service.run(application_id, fake_ai).analysis
    service.approve(analysis.id)

    with pytest.raises(NotReviewable):
        service.reject(analysis.id)
    with pytest.raises(NotReviewable):
        service.approve(analysis.id)

    shown = service.get_for_display(application_id)
    assert shown is not None and shown.analysis.status is ReviewStatus.APPROVED


def test_deciding_an_unknown_analysis_raises_not_found(
    db_session: Session, clock: FakeClock
) -> None:
    service = make_service(db_session, clock)

    with pytest.raises(AnalysisNotFound):
        service.approve(999)
    with pytest.raises(AnalysisNotFound):
        service.reject(999)


def test_two_decisions_at_once_cannot_both_win(
    db_session: Session,
    clock: FakeClock,
    fake_ai: FakeAIClient,
    test_engine: Engine,
) -> None:
    """Approved and rejected are final, even when two tabs decide the same draft together.

    Session A decides the row but has not committed. Session B's reject has to wait for A
    instead of reading the stale draft, and once A commits it finds the row already decided.
    """
    application_id = make_application(db_session)
    analysis_id = make_service(db_session, clock).run(application_id, fake_ai).analysis.id
    factory = sessionmaker(bind=test_engine)
    outcome: list[object] = []

    with factory() as session_a, factory() as session_b:
        locked = PostingAnalysisRepository(session_a).get_for_update(analysis_id)
        assert locked is not None
        apply_decision(locked, ReviewStatus.APPROVED, clock())  # not committed yet

        def reject_in_the_other_tab() -> None:
            try:
                outcome.append(make_service(session_b, clock).reject(analysis_id))
            except NotReviewable as error:
                outcome.append(error)

        thread = threading.Thread(target=reject_in_the_other_tab)
        thread.start()
        thread.join(timeout=0.5)
        assert thread.is_alive(), "the second decision did not wait for the first"

        session_a.commit()
        thread.join(timeout=5)

    assert not thread.is_alive()
    assert len(outcome) == 1 and isinstance(outcome[0], NotReviewable)
    with test_engine.connect() as conn:
        status = conn.execute(text("SELECT status FROM posting_analyses")).scalar_one()
    assert status == "approved"
