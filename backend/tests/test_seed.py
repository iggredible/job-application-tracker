"""The seed script: what it creates, that it is repeatable, and that the data obeys the rules the
services enforce. The seed writes stage and timeline rows directly (the documented exception to
`change_stage()`), so the history test replays every timeline against the transition table."""

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from statistics import mean

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select, text
from sqlalchemy.orm import Session, sessionmaker

from app.models import (
    AICall,
    AIFeature,
    Application,
    EventType,
    PostingAnalysis,
    Resume,
    ReviewStatus,
    Source,
    Stage,
    TimelineEvent,
)
from app.services.guardrail import FIELDS
from app.services.resume_review import Outcome, derive_outcome, edit_ratio
from app.services.staleness import is_stale
from app.services.submission import unsubmittable_reason
from app.services.transitions import TRANSITIONS
from scripts import seed as seed_module
from scripts.seed import SeedRefused, parse_args, seed
from tests.conftest import FakeClock

NOW = datetime(2026, 11, 19, 12, 0, tzinfo=UTC)
TABLES = ("applications", "timeline_events", "ai_calls", "resumes", "posting_analyses")


@pytest.fixture
def seeded(db_session: Session) -> Session:
    seed(db_session, now=NOW)
    return db_session


def all_applications(session: Session) -> list[Application]:
    return list(session.scalars(select(Application).order_by(Application.id)))


def events_by_application(session: Session) -> dict[int, list[TimelineEvent]]:
    query = select(TimelineEvent).order_by(TimelineEvent.created_at, TimelineEvent.id)
    grouped: dict[int, list[TimelineEvent]] = defaultdict(list)
    for event in session.scalars(query):
        grouped[event.application_id].append(event)
    return grouped


def tailored_resumes(session: Session) -> list[Resume]:
    query = select(Resume).where(Resume.ai_call_id.is_not(None)).order_by(Resume.id)
    return list(session.scalars(query))


def applied_at(events: list[TimelineEvent]) -> datetime | None:
    return next(
        (
            e.created_at
            for e in events
            if e.from_stage is Stage.SAVED and e.to_stage is Stage.APPLIED
        ),
        None,
    )


def got_a_response(events: list[TimelineEvent]) -> bool:
    """A later stage change after Applied other than Withdrawn (the definition feature 14 uses)."""
    after = applied_at(events)
    return after is not None and any(
        e.type is EventType.STAGE_CHANGE
        and e.created_at > after
        and e.to_stage not in (Stage.WITHDRAWN, Stage.APPLIED)
        for e in events
    )


def dump(engine: Engine) -> dict[str, list]:
    with engine.connect() as conn:
        return {
            table: [tuple(row) for row in conn.execute(text(f"SELECT * FROM {table} ORDER BY id"))]
            for table in TABLES
        }


# --- running it ----------------------------------------------------------------------------------


def test_seed_refuses_a_non_empty_database_without_reset(seeded: Session) -> None:
    with pytest.raises(SeedRefused):
        seed(seeded, now=NOW)

    assert len(all_applications(seeded)) >= 38  # nothing was added or removed


def test_seed_refuses_a_database_that_holds_only_a_base_resume(db_session: Session) -> None:
    db_session.add(Resume(content_markdown="# Mine", status=ReviewStatus.APPROVED))
    db_session.commit()

    with pytest.raises(SeedRefused):
        seed(db_session, now=NOW)


def test_seed_with_reset_truncates_and_seeds_again(seeded: Session) -> None:
    before = len(all_applications(seeded))

    seed(seeded, now=NOW, reset=True)

    assert len(all_applications(seeded)) == before
    assert min(a.id for a in all_applications(seeded)) == 1
    assert seeded.scalar(select(Resume).where(Resume.application_id.is_(None)).limit(1))


def test_seeding_twice_with_the_same_now_gives_identical_data(
    db_session: Session, test_engine: Engine
) -> None:
    seed(db_session, now=NOW)
    first = dump(test_engine)

    seed(db_session, now=NOW, reset=True)

    assert dump(test_engine) == first


def test_seed_rolls_back_when_it_fails_halfway(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    def explode(*args: object, **kwargs: object) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(seed_module.AICallRepository, "add", explode)

    with pytest.raises(RuntimeError):
        seed(db_session, now=NOW)

    assert db_session.scalar(select(Application).limit(1)) is None


def test_the_reset_flag_is_off_unless_passed() -> None:
    assert parse_args([]).reset is False
    assert parse_args(["--reset"]).reset is True


def test_main_refuses_then_resets(
    test_engine: Engine, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(seed_module, "get_session_factory", lambda: sessionmaker(bind=test_engine))

    assert seed_module.main([]) == 0
    assert seed_module.main([]) == 1
    assert "--reset" in capsys.readouterr().err
    assert seed_module.main(["--reset"]) == 0


# --- the applications and their timelines --------------------------------------------------------


def test_seed_creates_one_approved_base_resume_with_no_application(seeded: Session) -> None:
    bases = list(seeded.scalars(select(Resume).where(Resume.application_id.is_(None))))

    assert len(bases) == 1
    assert bases[0].status is ReviewStatus.APPROVED
    assert bases[0].ai_call_id is None
    assert "## Experience" in bases[0].content_markdown


def test_seed_creates_about_forty_applications_across_all_sources(seeded: Session) -> None:
    applications = all_applications(seeded)

    assert 38 <= len(applications) <= 42
    assert {a.source for a in applications} == set(Source)
    assert len({a.company for a in applications}) == len(applications)


def test_seed_leaves_a_spread_of_current_stages(seeded: Session) -> None:
    assert {a.stage for a in all_applications(seeded)} == set(Stage)


def test_every_seeded_stage_history_is_valid(seeded: Session) -> None:
    events = events_by_application(seeded)

    for application in all_applications(seeded):
        history = events[application.id]
        changes = [e for e in history if e.type is EventType.STAGE_CHANGE]

        assert changes[0].from_stage is None and changes[0].to_stage is Stage.SAVED
        for previous, current in zip(changes, changes[1:], strict=False):
            assert current.from_stage is previous.to_stage, application.company
            assert current.to_stage in TRANSITIONS[previous.to_stage], application.company
        assert changes[-1].to_stage is application.stage, application.company
        assert history[0] is changes[0]  # the first event is the one that created it
        assert application.created_at == history[0].created_at
        assert [e.created_at for e in history] == sorted(e.created_at for e in history)
        assert all(e.from_stage is None and e.to_stage is None for e in history if e.note)


def test_seeded_events_span_about_ten_weeks_and_none_are_in_the_future(seeded: Session) -> None:
    times = [e.created_at for events in events_by_application(seeded).values() for e in events]

    assert max(times) <= NOW
    assert NOW - timedelta(weeks=10, days=1) <= min(times) <= NOW - timedelta(weeks=8)


def test_seed_leaves_about_five_stale_applications(seeded: Session) -> None:
    events = events_by_application(seeded)

    stale = [
        a
        for a in all_applications(seeded)
        if is_stale(a.stage, max(e.created_at for e in events[a.id]), NOW)
    ]

    assert 4 <= len(stale) <= 6


# --- posting analyses, tailored resumes and the call log -----------------------------------------


def test_about_half_the_applications_have_an_approved_analysis_and_a_tailored_resume(
    seeded: Session,
) -> None:
    approved = set(
        seeded.scalars(
            select(PostingAnalysis.application_id).where(
                PostingAnalysis.status == ReviewStatus.APPROVED
            )
        )
    )
    tailored = {r.application_id for r in tailored_resumes(seeded)}

    assert 18 <= len(approved & tailored) <= 24
    assert tailored <= approved  # tailoring needs an approved analysis


def test_seeded_tailored_outcomes_are_mixed(seeded: Session) -> None:
    by_application: dict[int, list[Resume]] = defaultdict(list)
    for resume in sorted(
        tailored_resumes(seeded), key=lambda r: (r.created_at, r.id), reverse=True
    ):
        by_application[resume.application_id].append(resume)

    outcomes: dict[Outcome, int] = defaultdict(int)
    for resumes in by_application.values():
        for position, resume in enumerate(resumes):  # newest first, like the app does
            outcome = derive_outcome(
                resume.status, resume.draft_markdown, resume.content_markdown, position > 0
            )
            outcomes[outcome] += 1

    assert set(outcomes) == set(Outcome)
    assert 2 <= outcomes[Outcome.SUPERSEDED] <= 4  # "a few"


def test_some_seeded_tailored_resumes_carry_guardrail_flags(seeded: Session) -> None:
    flagged = [r for r in tailored_resumes(seeded) if r.guardrail_flags]

    assert 3 <= len(flagged) <= len(tailored_resumes(seeded)) / 2
    for resume in flagged:
        for flag in resume.guardrail_flags:
            assert set(flag) == {"field", "value", "message"}
            assert flag["field"] in FIELDS


def test_seeded_ai_rows_use_model_seed_with_prompt_versions_v1_and_v2(seeded: Session) -> None:
    calls = list(seeded.scalars(select(AICall)))

    assert {c.model for c in calls} == {"seed"}
    assert {c.prompt_version for c in calls} == {"v1", "v2"}
    assert {c.prompt_version for c in calls if c.feature is AIFeature.POSTING_ANALYSIS} == {"v1"}
    assert all(c.application_id is not None for c in calls)
    assert all(c.retrieved_example_ids == [] for c in calls)


def test_every_seeded_analysis_and_resume_links_to_its_own_ai_call(seeded: Session) -> None:
    for analysis in seeded.scalars(select(PostingAnalysis)):
        assert analysis.ai_call.feature is AIFeature.POSTING_ANALYSIS
        assert analysis.ai_call.application_id == analysis.application_id
        assert analysis.ai_call.response_json["keywords"] == analysis.keywords
    for resume in tailored_resumes(seeded):
        assert resume.ai_call.feature is AIFeature.TAILOR_RESUME
        assert resume.ai_call.application_id == resume.application_id
        assert resume.ai_call.response_json == resume.content_json
    used = {r.ai_call_id for r in tailored_resumes(seeded)} | set(
        seeded.scalars(select(PostingAnalysis.ai_call_id))
    )
    assert len(used) == len(tailored_resumes(seeded)) + seeded.query(PostingAnalysis).count()


def test_seeded_calls_carry_tokens_latency_and_cost_and_a_few_failed_ones_do_not(
    seeded: Session,
) -> None:
    calls = list(seeded.scalars(select(AICall)))
    failed = [c for c in calls if not c.schema_valid]

    assert 1 <= len(failed) <= 3
    for call in failed:
        assert call.response_json is None and call.error and call.estimated_cost is None
    for call in calls:
        if call.schema_valid:
            assert call.error is None and call.response_json is not None
            assert call.input_tokens and call.output_tokens and call.estimated_cost > 0
        assert call.latency_ms > 0


def test_v2_tailoring_has_lower_edit_ratios_and_fewer_flags_than_v1(seeded: Session) -> None:
    resumes = tailored_resumes(seeded)

    def ratios(version: str) -> list[float]:
        return [
            edit_ratio(r.draft_markdown, r.content_markdown)
            for r in resumes
            if r.ai_call.prompt_version == version and r.status is ReviewStatus.APPROVED
        ]

    def flags(version: str) -> list[int]:
        return [len(r.guardrail_flags) for r in resumes if r.ai_call.prompt_version == version]

    assert mean(ratios("v2")) < mean(ratios("v1"))
    assert mean(flags("v2")) < mean(flags("v1"))
    assert 0.15 <= mean(ratios("v1")) <= 0.45
    assert 0.03 <= mean(ratios("v2")) <= 0.25


def test_an_approved_resume_was_decided_after_it_was_made_and_a_draft_has_no_decision(
    seeded: Session,
) -> None:
    for resume in tailored_resumes(seeded):
        if resume.status is ReviewStatus.DRAFT:
            assert resume.reviewed_at is None and resume.content_markdown == resume.draft_markdown
        else:
            assert resume.created_at < resume.reviewed_at <= NOW
        assert resume.content_json is not None and resume.draft_markdown is not None


# --- the resume each application sent -------------------------------------------------------------


def test_submitted_resumes_follow_the_apply_rules(seeded: Session) -> None:
    events = events_by_application(seeded)
    base = seeded.scalar(select(Resume).where(Resume.application_id.is_(None)))

    for application in all_applications(seeded):
        sent_at = applied_at(events[application.id])
        if sent_at is None:  # still Saved, or withdrawn from Saved
            assert application.submitted_resume_id is None, application.company
            continue
        resume = seeded.get(Resume, application.submitted_resume_id)
        assert resume is not None and resume.status is ReviewStatus.APPROVED
        if resume.ai_call_id is None:  # a snapshot of the base resume, made for this application
            assert resume.application_id == application.id
            assert resume.content_markdown == base.content_markdown
            assert resume.draft_markdown is None and resume.content_json is None
            assert resume.created_at == sent_at
        else:
            assert unsubmittable_reason(resume, application.id) is None
            assert resume.reviewed_at <= sent_at


def test_the_stage_change_and_the_submitted_resume_agree_on_what_was_sent(seeded: Session) -> None:
    snapshots = list(
        seeded.scalars(
            select(Resume).where(Resume.application_id.is_not(None), Resume.ai_call_id.is_(None))
        )
    )

    assert snapshots  # some applications sent the base resume
    assert len({s.application_id for s in snapshots}) == len(snapshots)  # one each
    assert sum(1 for a in all_applications(seeded) if a.submitted_resume_id) > len(snapshots)


def test_the_tailored_response_rate_is_higher_than_the_base_rate(seeded: Session) -> None:
    events = events_by_application(seeded)
    sent = {"tailored": [], "base": []}
    for application in all_applications(seeded):
        if application.submitted_resume_id is None:
            continue
        resume = seeded.get(Resume, application.submitted_resume_id)
        kind = "tailored" if resume.ai_call_id is not None else "base"
        sent[kind].append(got_a_response(events[application.id]))

    assert len(sent["tailored"]) >= 10 and len(sent["base"]) >= 10
    assert mean(sent["tailored"]) > mean(sent["base"])
    assert 30 <= len(sent["tailored"]) + len(sent["base"]) <= 36  # about 34 of 40 applied


# --- it works with the real services -------------------------------------------------------------


def test_seeded_data_is_readable_through_the_applications_api(
    client: TestClient, db_session: Session, clock: FakeClock
) -> None:
    seed(db_session, now=clock.now)

    listing = client.get("/applications")

    assert listing.status_code == 200
    body = listing.json()
    assert 38 <= len(body["items"]) <= 42
    assert 4 <= body["stale_count"] <= 6
    for item in body["items"]:
        assert client.get(f"/applications/{item['id']}").status_code == 200
    tailored = {r.application_id for r in tailored_resumes(db_session)}
    for application_id in sorted(tailored)[:5]:
        drafts = client.get(f"/applications/{application_id}/tailored-resumes")
        assert drafts.status_code == 200 and drafts.json()
        assert client.get(f"/applications/{application_id}/coverage").status_code == 200
