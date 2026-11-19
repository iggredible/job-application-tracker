"""ApplicationService.apply(): one transaction for the snapshot, the pointer, the stage and the
timeline event, against the test database."""

import threading

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from app.models import Stage, TimelineEvent
from app.repositories.applications import ApplicationRepository
from app.repositories.posting_analyses import PostingAnalysisRepository
from app.repositories.resumes import ResumeRepository
from app.repositories.timeline import TimelineRepository
from app.schemas.application import ApplicationCreate
from app.services.applications import ApplicationService, GuardFailed, InvalidTransition
from app.services.resumes import ResumeService
from tests.conftest import FakeClock

S = Stage
BASE = "# Jordan Avery\n\n## Skills\nRuby on Rails\n"


def make_service(session: Session, clock: FakeClock) -> ApplicationService:
    return ApplicationService(
        ApplicationRepository(session),
        TimelineRepository(session),
        ResumeRepository(session),
        PostingAnalysisRepository(session),
        clock,
    )


@pytest.fixture
def service(db_session: Session, clock: FakeClock) -> ApplicationService:
    ResumeService(ResumeRepository(db_session), clock).save_base(BASE)
    return make_service(db_session, clock)


@pytest.fixture
def application_id(service: ApplicationService) -> int:
    data = ApplicationCreate(
        company="Northwind Freight",
        role="Senior Backend Engineer",
        source="linkedin",
        posting_text="Build services.",
    )
    return service.create(data).application.id


def snapshot_rows(engine: Engine) -> int:
    with engine.connect() as conn:
        query = text("SELECT count(*) FROM resumes WHERE application_id IS NOT NULL")
        return conn.execute(query).scalar_one()


def test_apply_with_the_base_resume_is_committed_as_one_unit(
    service: ApplicationService, application_id: int, test_engine: Engine, clock: FakeClock
) -> None:
    clock.advance(days=1)

    view = service.apply(application_id, "base", None)

    assert view.application.stage is S.APPLIED
    # A new session sees all four writes, so they were committed together.
    with test_engine.connect() as conn:
        application = conn.execute(
            text("SELECT stage, submitted_resume_id FROM applications WHERE id = :id"),
            {"id": application_id},
        ).one()
        snapshot = conn.execute(
            text("SELECT id, content_markdown FROM resumes WHERE application_id = :id"),
            {"id": application_id},
        ).one()
        events = (
            conn.execute(
                text("SELECT to_stage FROM timeline_events WHERE application_id = :id ORDER BY id"),
                {"id": application_id},
            )
            .scalars()
            .all()
        )
    assert application.stage == "applied"
    assert application.submitted_resume_id == snapshot.id
    assert snapshot.content_markdown == BASE
    assert events == ["saved", "applied"]


def test_apply_goes_through_change_stage_with_the_choice_in_the_context(
    service: ApplicationService, application_id: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple] = []
    original = ApplicationService.change_stage

    def spy(self, application_id, to_stage, *, context=None):  # noqa: ANN001, ANN202
        calls.append((to_stage, dict(context or {})))
        return original(self, application_id, to_stage, context=context)

    monkeypatch.setattr(ApplicationService, "change_stage", spy)

    service.apply(application_id, "base", None)

    assert calls == [(S.APPLIED, {"choice": "base", "resume_id": None})]


def test_a_failure_while_writing_the_event_leaves_no_snapshot_and_no_stage_change(
    service: ApplicationService,
    application_id: int,
    db_session: Session,
    test_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(self: TimelineRepository, event: TimelineEvent) -> TimelineEvent:
        raise RuntimeError("the event could not be written")

    monkeypatch.setattr(TimelineRepository, "add", fail)

    with pytest.raises(RuntimeError):
        service.apply(application_id, "base", None)

    db_session.rollback()  # what the request does when it ends with an error
    assert snapshot_rows(test_engine) == 0
    with test_engine.connect() as conn:
        row = conn.execute(
            text("SELECT stage, submitted_resume_id FROM applications WHERE id = :id"),
            {"id": application_id},
        ).one()
    assert (row.stage, row.submitted_resume_id) == ("saved", None)


def test_a_refused_apply_makes_no_snapshot(
    service: ApplicationService, application_id: int, test_engine: Engine
) -> None:
    with pytest.raises(GuardFailed):
        service.apply(application_id, None, None)

    assert snapshot_rows(test_engine) == 0


def test_a_refused_apply_releases_the_application_row_lock(
    service: ApplicationService, application_id: int, test_engine: Engine
) -> None:
    with pytest.raises(GuardFailed):
        service.apply(application_id, None, None)

    # Another transaction can lock the row at once (NOWAIT fails if the first still holds it).
    with sessionmaker(bind=test_engine)() as other:
        try:
            other.execute(
                text("SELECT id FROM applications WHERE id = :id FOR UPDATE NOWAIT"),
                {"id": application_id},
            )
        except OperationalError:  # pragma: no cover - the failure being tested
            pytest.fail("the refused apply still holds the application row lock")


def test_a_second_apply_is_refused_and_makes_no_second_snapshot(
    service: ApplicationService, application_id: int, test_engine: Engine
) -> None:
    service.apply(application_id, "base", None)

    with pytest.raises(InvalidTransition):
        service.apply(application_id, "base", None)

    assert snapshot_rows(test_engine) == 1


def test_two_applies_at_once_make_one_snapshot(
    service: ApplicationService, application_id: int, test_engine: Engine, clock: FakeClock
) -> None:
    """A double click, or two tabs, cannot apply twice or save two snapshots.

    Session A holds the application row. Session B's apply has to wait for it instead of reading
    the stale Saved stage, and once A has applied and committed, B finds the application already
    Applied and is refused.
    """
    factory = sessionmaker(bind=test_engine)
    outcome: list[object] = []

    with factory() as session_a, factory() as session_b:
        ApplicationRepository(session_a).get_for_update(application_id)  # A takes the row lock

        def apply_in_the_other_tab() -> None:
            try:
                outcome.append(make_service(session_b, clock).apply(application_id, "base", None))
            except InvalidTransition as error:
                outcome.append(error)

        thread = threading.Thread(target=apply_in_the_other_tab)
        thread.start()
        thread.join(timeout=0.5)
        assert thread.is_alive(), "the second apply did not wait for the first"

        make_service(session_a, clock).apply(application_id, "base", None)  # commits, unlocks
        thread.join(timeout=5)

    assert not thread.is_alive()
    assert len(outcome) == 1 and isinstance(outcome[0], InvalidTransition)
    assert snapshot_rows(test_engine) == 1


def test_the_submitted_resume_stays_after_later_stage_changes(
    service: ApplicationService, application_id: int
) -> None:
    submitted = service.apply(application_id, "base", None).submitted_resume

    later = service.change_stage(application_id, S.SCREENING)

    assert submitted is not None
    assert later.submitted_resume is not None
    assert later.submitted_resume.id == submitted.id
