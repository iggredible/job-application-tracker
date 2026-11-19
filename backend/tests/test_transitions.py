"""Transition table, guard structure and the stale rule. Pure logic: no database."""

from datetime import UTC, datetime, timedelta

import pytest

from app.models import PostingAnalysis, Resume, Stage
from app.services.staleness import STALE_AFTER_DAYS, idle_days, is_stale
from app.services.transitions import (
    GUARDS,
    TRANSITIONS,
    GuardContext,
    GuardFailure,
    allowed_next,
    require_approved_analysis,
    require_base_resume,
    run_guards,
)

S = Stage

# Written out here from the project overview, not read from the code under test.
EXPECTED: dict[Stage, list[Stage]] = {
    S.SAVED: [S.APPLIED, S.WITHDRAWN],
    S.APPLIED: [S.SCREENING, S.INTERVIEWING, S.REJECTED, S.WITHDRAWN],
    S.SCREENING: [S.INTERVIEWING, S.REJECTED, S.WITHDRAWN],
    S.INTERVIEWING: [S.OFFER, S.REJECTED, S.WITHDRAWN],
    S.OFFER: [S.ACCEPTED, S.REJECTED, S.WITHDRAWN],
    S.ACCEPTED: [],
    S.REJECTED: [],
    S.WITHDRAWN: [],
}
ALLOWED = [(a, b) for a, targets in EXPECTED.items() for b in targets]
DISALLOWED_SAMPLE = [
    (S.SAVED, S.SCREENING),
    (S.SAVED, S.INTERVIEWING),
    (S.SAVED, S.OFFER),
    (S.SAVED, S.ACCEPTED),
    (S.SAVED, S.REJECTED),
    (S.APPLIED, S.SAVED),
    (S.APPLIED, S.OFFER),
    (S.APPLIED, S.ACCEPTED),
    (S.SCREENING, S.APPLIED),
    (S.SCREENING, S.OFFER),
    (S.INTERVIEWING, S.SCREENING),
    (S.INTERVIEWING, S.ACCEPTED),
    (S.OFFER, S.INTERVIEWING),
    (S.OFFER, S.SAVED),
]
TERMINAL = [S.ACCEPTED, S.REJECTED, S.WITHDRAWN]


@pytest.mark.parametrize(("source", "target"), ALLOWED)
def test_every_allowed_transition_is_in_the_table(source: Stage, target: Stage) -> None:
    assert target in allowed_next(source)


@pytest.mark.parametrize(("source", "target"), DISALLOWED_SAMPLE)
def test_disallowed_transitions_are_not_in_the_table(source: Stage, target: Stage) -> None:
    assert target not in allowed_next(source)


@pytest.mark.parametrize("stage", list(Stage))
def test_a_stage_cannot_move_to_itself(stage: Stage) -> None:
    assert stage not in allowed_next(stage)


@pytest.mark.parametrize("stage", TERMINAL)
def test_terminal_stages_have_no_next_stages(stage: Stage) -> None:
    assert allowed_next(stage) == []


def test_allowed_next_stages_match_the_overview_table_and_keep_stage_order() -> None:
    assert {stage: allowed_next(stage) for stage in Stage} == EXPECTED


def test_every_stage_has_an_entry_in_the_transition_table() -> None:
    assert set(TRANSITIONS) == set(Stage)


def test_the_registered_guards_are_for_tailoring_and_for_applying() -> None:
    assert set(GUARDS) == {"start_tailoring", (S.SAVED, S.APPLIED)}
    assert GUARDS["start_tailoring"] == [require_approved_analysis, require_base_resume]


def test_every_other_transition_has_no_guard() -> None:
    for source, targets in TRANSITIONS.items():
        for target in targets:
            if (source, target) != (S.SAVED, S.APPLIED):
                assert run_guards((source, target), GuardContext(application=None)) is None


def test_saved_to_applied_needs_a_choice() -> None:
    failure = run_guards((S.SAVED, S.APPLIED), GuardContext(application=None))

    assert failure == GuardFailure("Choose the resume you sent.")


def test_tailoring_needs_an_approved_analysis() -> None:
    analysis = PostingAnalysis(keywords=["go"])

    assert require_approved_analysis(GuardContext(application=None)) == GuardFailure(
        "The posting analysis must be approved before tailoring."
    )
    context = GuardContext(application=None, approved_analysis=analysis)
    assert require_approved_analysis(context) is None


def test_tailoring_needs_a_base_resume() -> None:
    resume = Resume(content_markdown="## Skills")

    assert require_base_resume(GuardContext(application=None)) == GuardFailure(
        "Save a base resume before tailoring."
    )
    assert require_base_resume(GuardContext(application=None, base_resume=resume)) is None


def test_the_analysis_guard_runs_before_the_base_resume_guard() -> None:
    failure = run_guards("start_tailoring", GuardContext(application=None))

    assert failure == require_approved_analysis(GuardContext(application=None))
    ready = GuardContext(
        application=None,
        approved_analysis=PostingAnalysis(keywords=[]),
        base_resume=Resume(content_markdown="x"),
    )
    assert run_guards("start_tailoring", ready) is None


def test_a_failing_guard_is_reported_with_its_reason(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(context: GuardContext) -> GuardFailure:
        return GuardFailure("no resume chosen")

    monkeypatch.setitem(GUARDS, (S.SAVED, S.APPLIED), [refuse])

    failure = run_guards((S.SAVED, S.APPLIED), GuardContext(application=None))

    assert failure == GuardFailure("no resume chosen")
    # A guard keyed to one action does not affect another.
    assert run_guards((S.SAVED, S.WITHDRAWN), GuardContext(application=None)) is None


def test_guards_can_be_keyed_by_a_non_transition_action(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(GUARDS, "start_tailoring", [lambda context: GuardFailure("not approved")])

    assert run_guards("start_tailoring", GuardContext(application=None)) == GuardFailure(
        "not approved"
    )


def test_the_first_failing_guard_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(
        GUARDS,
        (S.SAVED, S.APPLIED),
        [lambda c: None, lambda c: GuardFailure("first"), lambda c: GuardFailure("second")],
    )

    assert run_guards((S.SAVED, S.APPLIED), GuardContext(application=None)) == GuardFailure("first")


NOW = datetime(2026, 11, 18, 12, 0, tzinfo=UTC)


def test_stale_threshold_is_14_days() -> None:
    assert STALE_AFTER_DAYS == 14


def test_not_stale_at_13_days_stale_at_14() -> None:
    assert not is_stale(S.APPLIED, NOW - timedelta(days=13, hours=23), NOW)
    assert is_stale(S.APPLIED, NOW - timedelta(days=14), NOW)
    assert is_stale(S.APPLIED, NOW - timedelta(days=40), NOW)


@pytest.mark.parametrize("stage", TERMINAL)
def test_terminal_stage_is_never_stale(stage: Stage) -> None:
    assert not is_stale(stage, NOW - timedelta(days=100), NOW)


@pytest.mark.parametrize("stage", [S.SAVED, S.APPLIED, S.SCREENING, S.INTERVIEWING, S.OFFER])
def test_every_non_terminal_stage_can_go_stale(stage: Stage) -> None:
    assert is_stale(stage, NOW - timedelta(days=14), NOW)


def test_idle_days_counts_whole_days_rounded_down() -> None:
    assert idle_days(NOW, NOW) == 0
    assert idle_days(NOW - timedelta(hours=23), NOW) == 0
    assert idle_days(NOW - timedelta(days=18, hours=23), NOW) == 18
    assert idle_days(NOW - timedelta(days=20), NOW) == 20


def test_idle_days_is_never_negative() -> None:
    assert idle_days(NOW + timedelta(hours=1), NOW) == 0
