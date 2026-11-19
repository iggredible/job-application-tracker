"""change_stage(), notes, the timeline and the derived list values, against the test database."""

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import EventType, Stage, TimelineEvent
from app.repositories.applications import ApplicationRepository
from app.repositories.posting_analyses import PostingAnalysisRepository
from app.repositories.resumes import ResumeRepository
from app.repositories.timeline import TimelineRepository
from app.schemas.application import ApplicationCreate, ApplicationUpdate
from app.services.applications import (
    ApplicationNotFound,
    ApplicationService,
    GuardFailed,
    InvalidTransition,
)
from app.services.resumes import ResumeService
from app.services.transitions import GUARDS, GuardFailure
from tests.conftest import FakeClock

S = Stage


def make_service(session: Session, clock: FakeClock) -> ApplicationService:
    # A base resume exists, so a Saved application can be applied with it (feature 11).
    ResumeService(ResumeRepository(session), clock).save_base("# Jordan Avery\n")
    return ApplicationService(
        ApplicationRepository(session),
        TimelineRepository(session),
        ResumeRepository(session),
        PostingAnalysisRepository(session),
        clock,
    )


def move(service: ApplicationService, application_id: int, stage: Stage):  # noqa: ANN201
    """Saved -> Applied goes through the apply action (with the base resume); the rest through
    change_stage()."""
    if stage is S.APPLIED:
        return service.apply(application_id, "base", None)
    return service.change_stage(application_id, stage)


def make_application(service: ApplicationService, **overrides) -> int:
    data = {
        "company": "Northwind Freight",
        "role": "Senior Backend Engineer",
        "source": "linkedin",
        "posting_text": "Build services.",
    }
    return service.create(ApplicationCreate(**{**data, **overrides})).application.id


def event_rows(session: Session, application_id: int) -> list[tuple]:
    """Oldest first, as (type, from_stage, to_stage, note, created_at)."""
    query = (
        select(TimelineEvent)
        .where(TimelineEvent.application_id == application_id)
        .order_by(TimelineEvent.id)
    )
    return [
        (e.type, e.from_stage, e.to_stage, e.note, e.created_at) for e in session.scalars(query)
    ]


def test_create_writes_the_initial_saved_event(db_session: Session, clock: FakeClock) -> None:
    service = make_service(db_session, clock)

    application_id = make_application(service)

    assert event_rows(db_session, application_id) == [
        (EventType.STAGE_CHANGE, None, S.SAVED, None, clock.now)
    ]


def test_change_stage_updates_stage_and_writes_event_with_clock_time(
    db_session: Session, clock: FakeClock
) -> None:
    service = make_service(db_session, clock)
    application_id = make_application(service)
    created_at = clock.now
    clock.advance(days=2)

    view = move(service, application_id, S.APPLIED)

    assert view.application.stage is S.APPLIED
    assert event_rows(db_session, application_id) == [
        (EventType.STAGE_CHANGE, None, S.SAVED, None, created_at),
        (EventType.STAGE_CHANGE, S.SAVED, S.APPLIED, None, clock.now),
    ]


def test_change_stage_is_visible_to_a_new_session(db_session: Session, clock: FakeClock) -> None:
    service = make_service(db_session, clock)
    application_id = make_application(service)

    service.change_stage(application_id, S.WITHDRAWN)

    with Session(db_session.get_bind()) as other:
        reloaded = ApplicationRepository(other).get(application_id)
        assert reloaded is not None
        assert reloaded.stage is S.WITHDRAWN


def test_a_walk_through_the_pipeline_records_every_step(
    db_session: Session, clock: FakeClock
) -> None:
    service = make_service(db_session, clock)
    application_id = make_application(service)

    for stage in (S.APPLIED, S.SCREENING, S.INTERVIEWING, S.OFFER, S.ACCEPTED):
        clock.advance(days=1)
        move(service, application_id, stage)

    steps = [(e[1], e[2]) for e in event_rows(db_session, application_id)]
    assert steps == [
        (None, S.SAVED),
        (S.SAVED, S.APPLIED),
        (S.APPLIED, S.SCREENING),
        (S.SCREENING, S.INTERVIEWING),
        (S.INTERVIEWING, S.OFFER),
        (S.OFFER, S.ACCEPTED),
    ]


def test_failed_transition_writes_nothing(db_session: Session, clock: FakeClock) -> None:
    service = make_service(db_session, clock)
    application_id = make_application(service)

    with pytest.raises(InvalidTransition) as raised:
        service.change_stage(application_id, S.OFFER)

    # Applied is not offered: it happens through the apply action.
    assert raised.value.allowed == [S.WITHDRAWN]
    db_session.expire_all()
    assert service.get(application_id).application.stage is S.SAVED
    assert len(event_rows(db_session, application_id)) == 1


def test_moving_to_the_same_stage_is_rejected(db_session: Session, clock: FakeClock) -> None:
    service = make_service(db_session, clock)
    application_id = make_application(service)

    with pytest.raises(InvalidTransition):
        service.change_stage(application_id, S.SAVED)

    assert len(event_rows(db_session, application_id)) == 1


def test_terminal_stage_rejects_every_move_and_writes_nothing(
    db_session: Session, clock: FakeClock
) -> None:
    service = make_service(db_session, clock)
    application_id = make_application(service)
    service.change_stage(application_id, S.WITHDRAWN)

    for target in Stage:
        with pytest.raises(InvalidTransition) as raised:
            service.change_stage(application_id, target)
        assert raised.value.allowed == []

    assert len(event_rows(db_session, application_id)) == 2


def test_a_failing_guard_blocks_the_move_and_writes_nothing(
    db_session: Session, clock: FakeClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = make_service(db_session, clock)
    application_id = make_application(service)
    monkeypatch.setitem(GUARDS, (S.SAVED, S.APPLIED), [lambda c: GuardFailure("no resume chosen")])

    with pytest.raises(GuardFailed) as raised:
        service.change_stage(application_id, S.APPLIED)

    assert raised.value.reason == "no resume chosen"
    db_session.expire_all()
    assert service.get(application_id).application.stage is S.SAVED
    assert len(event_rows(db_session, application_id)) == 1


def test_guards_receive_the_application_and_the_extra_input(
    db_session: Session, clock: FakeClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = make_service(db_session, clock)
    application_id = make_application(service)
    seen = []

    def spy(context):
        seen.append(context)

    monkeypatch.setitem(GUARDS, (S.SAVED, S.WITHDRAWN), [spy])
    service.change_stage(application_id, S.WITHDRAWN, context={"resume_id": 7})

    assert seen[0].application.id == application_id
    assert seen[0].extra == {"resume_id": 7}


def test_stage_and_event_are_committed_together(
    db_session: Session, clock: FakeClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = make_service(db_session, clock)
    application_id = make_application(service)

    def boom(self, event):
        raise RuntimeError("event insert failed")

    monkeypatch.setattr(TimelineRepository, "add", boom)
    with pytest.raises(RuntimeError):
        service.change_stage(application_id, S.WITHDRAWN)

    # Nothing was committed: a second session still sees the old stage and one event.
    with Session(db_session.get_bind()) as other:
        reloaded = ApplicationRepository(other).get(application_id)
        assert reloaded is not None
        assert reloaded.stage is S.SAVED
        assert other.scalar(select(func.count()).select_from(TimelineEvent)) == 1


def test_change_stage_for_a_missing_application_raises_not_found(
    db_session: Session, clock: FakeClock
) -> None:
    with pytest.raises(ApplicationNotFound):
        make_service(db_session, clock).change_stage(999, S.APPLIED)


def test_add_note_writes_a_note_event_and_keeps_the_stage(
    db_session: Session, clock: FakeClock
) -> None:
    service = make_service(db_session, clock)
    application_id = make_application(service)
    clock.advance(hours=3)

    event = service.add_note(application_id, "Phone screen booked for Thursday")

    assert (event.type, event.from_stage, event.to_stage) == (EventType.NOTE, None, None)
    assert event.note == "Phone screen booked for Thursday"
    assert event.created_at == clock.now
    assert service.get(application_id).application.stage is S.SAVED


def test_add_note_for_a_missing_application_raises_not_found(
    db_session: Session, clock: FakeClock
) -> None:
    with pytest.raises(ApplicationNotFound):
        make_service(db_session, clock).add_note(999, "hello")


def test_timeline_is_newest_first_with_id_as_the_tiebreak(
    db_session: Session, clock: FakeClock
) -> None:
    service = make_service(db_session, clock)
    application_id = make_application(service)
    service.add_note(application_id, "same instant as creation")
    clock.advance(days=1)
    move(service, application_id, S.APPLIED)

    events = service.timeline(application_id)

    assert [(e.type, e.note) for e in events] == [
        (EventType.STAGE_CHANGE, None),
        (EventType.NOTE, "same instant as creation"),
        (EventType.STAGE_CHANGE, None),
    ]
    assert events[0].to_stage is S.APPLIED
    assert events[2].to_stage is S.SAVED


def test_timeline_for_a_missing_application_raises_not_found(
    db_session: Session, clock: FakeClock
) -> None:
    with pytest.raises(ApplicationNotFound):
        make_service(db_session, clock).timeline(999)


def test_a_new_application_has_last_activity_now_and_is_not_stale(
    db_session: Session, clock: FakeClock
) -> None:
    service = make_service(db_session, clock)
    application_id = make_application(service)

    view = service.get(application_id)

    assert view.last_activity_at == clock.now
    assert (view.is_stale, view.idle_days) == (False, 0)
    assert view.allowed_next_stages == [S.WITHDRAWN]


def test_last_activity_is_the_newest_timeline_event(db_session: Session, clock: FakeClock) -> None:
    service = make_service(db_session, clock)
    application_id = make_application(service)
    clock.advance(days=3)
    service.add_note(application_id, "recruiter emailed")

    assert service.get(application_id).last_activity_at == clock.now


def test_stale_rule_uses_the_injected_clock(db_session: Session, clock: FakeClock) -> None:
    service = make_service(db_session, clock)
    application_id = make_application(service)

    clock.advance(days=13)
    view = service.get(application_id)
    assert (view.is_stale, view.idle_days) == (False, 13)

    clock.advance(days=1)
    view = service.get(application_id)
    assert (view.is_stale, view.idle_days) == (True, 14)

    clock.advance(days=6)
    view = service.get(application_id)
    assert (view.is_stale, view.idle_days) == (True, 20)


def test_a_terminal_application_is_never_stale(db_session: Session, clock: FakeClock) -> None:
    service = make_service(db_session, clock)
    application_id = make_application(service)
    service.change_stage(application_id, S.WITHDRAWN)

    clock.advance(days=60)

    assert service.get(application_id).is_stale is False


def test_a_note_resets_the_stale_clock(db_session: Session, clock: FakeClock) -> None:
    service = make_service(db_session, clock)
    application_id = make_application(service)
    clock.advance(days=20)
    assert service.get(application_id).is_stale is True

    service.add_note(application_id, "followed up by email")

    view = service.get(application_id)
    assert (view.is_stale, view.idle_days) == (False, 0)
    assert view.last_activity_at == clock.now


def test_editing_an_application_is_not_activity(db_session: Session, clock: FakeClock) -> None:
    service = make_service(db_session, clock)
    application_id = make_application(service)
    clock.advance(days=20)

    service.update(application_id, ApplicationUpdate(role="Staff Engineer"))

    assert service.get(application_id).is_stale is True


def test_list_counts_every_stage_even_when_empty(db_session: Session, clock: FakeClock) -> None:
    service = make_service(db_session, clock)

    result = service.list()

    assert result.items == []
    assert result.counts_by_stage == dict.fromkeys(Stage, 0)
    assert list(result.counts_by_stage) == list(Stage)
    assert result.stale_count == 0


def test_list_counts_cover_all_applications_when_filtered(
    db_session: Session, clock: FakeClock
) -> None:
    service = make_service(db_session, clock)
    a = make_application(service, company="A")
    b = make_application(service, company="B")
    make_application(service, company="C")
    move(service, a, S.APPLIED)
    move(service, b, S.APPLIED)
    service.change_stage(b, S.REJECTED)

    everything = service.list()
    only_applied = service.list(stage=S.APPLIED)

    assert [v.application.id for v in only_applied.items] == [a]
    assert len(everything.items) == 3
    expected = {**dict.fromkeys(Stage, 0), S.SAVED: 1, S.APPLIED: 1, S.REJECTED: 1}
    assert only_applied.counts_by_stage == expected
    assert everything.counts_by_stage == expected


def test_stale_count_covers_all_applications_and_skips_terminal_ones(
    db_session: Session, clock: FakeClock
) -> None:
    service = make_service(db_session, clock)
    old_open = make_application(service, company="Old open")
    old_closed = make_application(service, company="Old closed")
    service.change_stage(old_closed, S.WITHDRAWN)
    clock.advance(days=20)
    fresh = make_application(service, company="Fresh")
    move(service, fresh, S.APPLIED)

    result = service.list(stage=S.APPLIED)

    assert result.stale_count == 1  # only "Old open", though the filter shows just "Fresh"
    assert [v.application.company for v in result.items] == ["Fresh"]
    assert service.get(old_open).is_stale is True
    assert service.get(old_closed).is_stale is False


def test_list_items_carry_the_derived_fields(db_session: Session, clock: FakeClock) -> None:
    service = make_service(db_session, clock)
    make_application(service)
    clock.advance(days=18)

    [view] = service.list().items

    assert (view.is_stale, view.idle_days) == (True, 18)
    assert view.allowed_next_stages == [S.WITHDRAWN]
