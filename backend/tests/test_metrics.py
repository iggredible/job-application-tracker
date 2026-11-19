"""The metric calculations (feature 14), on small hand-built datasets with known answers.

Nothing here touches the database: stage changes and AI rows are built by hand, so each test
states exactly what exists and what the answer must be.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from app.models import AIFeature, PostingAnalysis, Resume, ReviewStatus, Stage
from app.repositories.ai_calls import AICallRow
from app.repositories.timeline import StageChange
from app.services.metrics import (
    ai_rows,
    applied_ids,
    funnel,
    responded_ids,
    time_in_stage,
)

S = Stage
T0 = datetime(2026, 11, 1, tzinfo=UTC)


def change(application_id: int, to_stage: Stage, day: float) -> StageChange:
    """The application moved to `to_stage` `day` days after T0. The metrics read only the
    order of an application's changes and their times, so `from_stage` is not needed."""
    return StageChange(application_id, None, to_stage, T0 + timedelta(days=day))


# --- funnel -------------------------------------------------------------------------------------


def test_a_later_stage_counts_as_passing_the_earlier_ones() -> None:
    # Applied -> Interviewing skips Screening, and still counts at Screening.
    changes = [
        change(1, S.SAVED, 0),
        change(1, S.APPLIED, 1),
        change(1, S.INTERVIEWING, 2),
        change(1, S.REJECTED, 3),
    ]

    steps = {step.stage: step.count for step in funnel(changes)}

    assert steps == {S.APPLIED: 1, S.SCREENING: 1, S.INTERVIEWING: 1, S.OFFER: 0}


def test_the_funnel_counts_applications_and_the_share_that_moved_on() -> None:
    changes = [
        # 1 went all the way.
        *[
            change(1, stage, i)
            for i, stage in enumerate(
                [S.SAVED, S.APPLIED, S.SCREENING, S.INTERVIEWING, S.OFFER, S.ACCEPTED]
            )
        ],
        # 2 skipped Screening, then was rejected.
        *[
            change(2, stage, i)
            for i, stage in enumerate([S.SAVED, S.APPLIED, S.INTERVIEWING, S.REJECTED])
        ],
        # 3 was rejected right after applying.
        *[change(3, stage, i) for i, stage in enumerate([S.SAVED, S.APPLIED, S.REJECTED])],
        # 4 was withdrawn from Saved and 5 is still in Saved: neither applied.
        change(4, S.SAVED, 0),
        change(4, S.WITHDRAWN, 1),
        change(5, S.SAVED, 0),
    ]

    steps = funnel(changes)

    assert [(s.stage, s.count, s.share_of_previous) for s in steps] == [
        (S.APPLIED, 3, None),
        (S.SCREENING, 2, 2 / 3),
        (S.INTERVIEWING, 2, 1.0),
        (S.OFFER, 1, 0.5),
    ]


def test_accepted_counts_at_offer() -> None:
    changes = [change(1, S.SAVED, 0), change(1, S.APPLIED, 1), change(1, S.ACCEPTED, 2)]

    assert {step.stage: step.count for step in funnel(changes)}[S.OFFER] == 1


def test_the_share_that_moved_on_is_null_when_the_step_before_is_empty() -> None:
    changes = [change(1, S.SAVED, 0), change(1, S.APPLIED, 1)]

    steps = {step.stage: step.share_of_previous for step in funnel(changes)}

    assert steps == {S.APPLIED: None, S.SCREENING: 0.0, S.INTERVIEWING: None, S.OFFER: None}


def test_an_empty_timeline_gives_a_funnel_of_zeros() -> None:
    assert [(s.stage, s.count, s.share_of_previous) for s in funnel([])] == [
        (S.APPLIED, 0, None),
        (S.SCREENING, 0, None),
        (S.INTERVIEWING, 0, None),
        (S.OFFER, 0, None),
    ]


# --- time in stage ------------------------------------------------------------------------------


def test_only_completed_intervals_count_and_each_stage_has_a_median_and_a_sample_size() -> None:
    changes = [
        # 1: Saved 2 days, Applied 4, Screening 6, Interviewing 2, Offer 6. Accepted is terminal.
        *[
            change(1, stage, day)
            for stage, day in [
                (S.SAVED, 0),
                (S.APPLIED, 2),
                (S.SCREENING, 6),
                (S.INTERVIEWING, 12),
                (S.OFFER, 14),
                (S.ACCEPTED, 20),
            ]
        ],
        # 2: Saved 4 days, Applied 6. Rejected is terminal.
        *[change(2, stage, day) for stage, day in [(S.SAVED, 0), (S.APPLIED, 4), (S.REJECTED, 10)]],
        # 3: Saved 1 day, Applied 2. It is still in Screening, which has no end yet.
        *[change(3, stage, day) for stage, day in [(S.SAVED, 0), (S.APPLIED, 1), (S.SCREENING, 3)]],
        # 4: still in Saved.
        change(4, S.SAVED, 0),
    ]

    result = {row.stage: (row.median_days, row.sample_size) for row in time_in_stage(changes)}

    assert result == {
        S.SAVED: (2.0, 3),  # 2, 4, 1
        S.APPLIED: (4.0, 3),  # 4, 6, 2
        S.SCREENING: (6.0, 1),  # only application 1 left it
        S.INTERVIEWING: (2.0, 1),
        S.OFFER: (6.0, 1),
    }


def test_the_stages_listed_are_the_ones_that_can_be_left_in_stage_order() -> None:
    assert [row.stage for row in time_in_stage([])] == [
        S.SAVED,
        S.APPLIED,
        S.SCREENING,
        S.INTERVIEWING,
        S.OFFER,
    ]


def test_the_median_of_an_even_sample_is_the_mean_of_the_middle_two() -> None:
    changes = [
        *[
            change(i, stage, day)
            for i, days in enumerate([1, 2, 3, 4], start=1)
            for stage, day in [(S.SAVED, 0), (S.APPLIED, days)]
        ],
    ]

    saved = next(row for row in time_in_stage(changes) if row.stage is S.SAVED)

    assert (saved.median_days, saved.sample_size) == (2.5, 4)


def test_days_are_not_rounded() -> None:
    changes = [change(1, S.SAVED, 0), change(1, S.APPLIED, 1.5)]

    saved = next(row for row in time_in_stage(changes) if row.stage is S.SAVED)

    assert saved.median_days == 1.5


def test_days_across_a_daylight_saving_change_are_exact() -> None:
    # The database returns datetimes in its session time zone, all sharing one tzinfo. Python
    # subtracts those by wall-clock time, so 14 days across the 1 Nov 2026 clock change would
    # read as 14 days less an hour unless the times are converted first.
    zone = ZoneInfo("America/Los_Angeles")
    before = datetime(2026, 10, 25, 12, 0, tzinfo=zone)
    after = before + timedelta(days=14)  # wall-clock arithmetic: 8 Nov 12:00, 14 days 1 hour later
    assert (after.astimezone(UTC) - before.astimezone(UTC)) == timedelta(days=14, hours=1)
    changes = [
        StageChange(1, None, S.SAVED, before.astimezone(UTC).astimezone(zone)),
        StageChange(1, S.SAVED, S.APPLIED, after.astimezone(UTC).astimezone(zone)),
    ]

    saved = next(row for row in time_in_stage(changes) if row.stage is S.SAVED)

    assert saved.median_days == pytest.approx(14 + 1 / 24)


def test_a_stage_nobody_left_has_no_median_and_a_sample_of_zero() -> None:
    changes = [change(1, S.SAVED, 0), change(1, S.APPLIED, 2)]

    offer = next(row for row in time_in_stage(changes) if row.stage is S.OFFER)

    assert (offer.median_days, offer.sample_size) == (None, 0)


# --- who applied and who responded --------------------------------------------------------------


def test_a_response_is_a_later_stage_change_other_than_withdrawn() -> None:
    changes = [
        # 1: a screening, a response.
        change(1, S.SAVED, 0),
        change(1, S.APPLIED, 1),
        change(1, S.SCREENING, 5),
        # 2: a rejection is a response too.
        change(2, S.SAVED, 0),
        change(2, S.APPLIED, 1),
        change(2, S.REJECTED, 5),
        # 3: withdrawn after applying is not.
        change(3, S.SAVED, 0),
        change(3, S.APPLIED, 1),
        change(3, S.WITHDRAWN, 5),
        # 4: nothing since applying.
        change(4, S.SAVED, 0),
        change(4, S.APPLIED, 1),
        # 5: never applied.
        change(5, S.SAVED, 0),
        change(5, S.WITHDRAWN, 1),
    ]

    assert applied_ids(changes) == {1, 2, 3, 4}
    assert responded_ids(changes) == {1, 2}


def test_a_response_followed_by_a_withdrawal_still_counts() -> None:
    changes = [
        change(1, S.SAVED, 0),
        change(1, S.APPLIED, 1),
        change(1, S.SCREENING, 5),
        change(1, S.WITHDRAWN, 9),
    ]

    assert responded_ids(changes) == {1}


# --- AI rows ------------------------------------------------------------------------------------

POSTING = AIFeature.POSTING_ANALYSIS
TAILOR = AIFeature.TAILOR_RESUME


def call(
    call_id: int,
    feature: AIFeature = TAILOR,
    *,
    version: str = "v1",
    model: str = "m",
    failed: bool = False,
    latency_ms: int = 1000,
) -> AICallRow:
    return AICallRow(
        id=call_id,
        feature=feature,
        prompt_version=version,
        model=model,
        error="api_error: boom" if failed else None,
        input_tokens=None if failed else 100,
        output_tokens=None if failed else 50,
        estimated_cost=None if failed else Decimal("0.01"),
        latency_ms=latency_ms,
    )


def resume(
    resume_id: int,
    application_id: int,
    call_id: int,
    status: ReviewStatus,
    *,
    draft: str = "abcd",
    content: str | None = None,
    flags: int = 0,
    day: int = 0,
) -> Resume:
    return Resume(
        id=resume_id,
        application_id=application_id,
        ai_call_id=call_id,
        status=status,
        draft_markdown=draft,
        content_markdown=draft if content is None else content,
        guardrail_flags=[
            {"field": "skill", "value": f"s{i}", "message": "m"} for i in range(flags)
        ],
        created_at=T0 + timedelta(days=day),
    )


def analysis(
    analysis_id: int, application_id: int, call_id: int, status: ReviewStatus, *, day: int = 0
) -> PostingAnalysis:
    return PostingAnalysis(
        id=analysis_id,
        application_id=application_id,
        ai_call_id=call_id,
        requirements=[],
        keywords=[],
        status=status,
        created_at=T0 + timedelta(days=day),
    )


APPROVED, REJECTED, DRAFT = ReviewStatus.APPROVED, ReviewStatus.REJECTED, ReviewStatus.DRAFT


def test_tailor_resume_rows_count_calls_outcomes_edit_ratio_and_flags() -> None:
    calls = [
        call(1, latency_ms=1000),
        call(2, latency_ms=2000),
        call(3, latency_ms=3000),
        call(4, latency_ms=4000),
        call(5, latency_ms=5000),
        call(6, latency_ms=6000),
        call(7, failed=True, latency_ms=7000),
    ]
    resumes = [
        resume(1, 1, 1, APPROVED, flags=0),  # approved as is
        resume(2, 2, 2, APPROVED, draft="abcd", content="abxx", flags=2),  # edited ratio 0.5
        resume(3, 3, 3, REJECTED, flags=1),
        resume(4, 4, 4, DRAFT, flags=3),  # pending
        resume(5, 5, 5, DRAFT, flags=0, day=0),  # superseded by the next one
        resume(6, 5, 6, DRAFT, flags=0, day=1),  # pending
    ]

    (row,) = ai_rows(calls, resumes, [])

    assert (row.feature, row.prompt_version, row.model) == (TAILOR, "v1", "m")
    assert (row.calls, row.failed_calls) == (7, 1)
    assert (row.approved_as_is, row.edited_then_approved, row.rejected) == (1, 1, 1)
    assert (row.pending, row.superseded) == (2, 1)
    # Edit ratio is over the approved resumes: 0 and 0.5.
    assert row.avg_edit_ratio == pytest.approx(0.25)
    # Flags are over every draft: 0, 2, 1, 3, 0, 0.
    assert row.avg_flags_per_draft == pytest.approx(1.0)
    # Failed calls have no tokens or cost; the latency of every call counts.
    assert (row.input_tokens, row.output_tokens) == (600, 300)
    assert row.estimated_cost == pytest.approx(0.06)
    assert row.median_latency_ms == 4000


def test_a_decided_resume_is_never_superseded_by_a_newer_draft() -> None:
    calls = [call(1), call(2)]
    resumes = [
        resume(1, 1, 1, APPROVED, day=0),
        resume(2, 1, 2, DRAFT, day=1),
    ]

    (row,) = ai_rows(calls, resumes, [])

    assert (row.approved_as_is, row.pending, row.superseded) == (1, 1, 0)


def test_rows_are_split_by_feature_prompt_version_and_model() -> None:
    calls = [
        call(1, TAILOR, version="v1", model="m"),
        call(2, TAILOR, version="v1", model="seed"),
        call(3, TAILOR, version="v2", model="m"),
        call(4, POSTING, version="v1", model="m"),
    ]
    resumes = [
        resume(1, 1, 1, APPROVED),
        resume(2, 2, 2, APPROVED),
        resume(3, 3, 3, APPROVED, draft="abcd", content="abxx"),
    ]
    analyses = [analysis(1, 4, 4, APPROVED)]

    rows = ai_rows(calls, resumes, analyses)

    assert [(r.feature, r.prompt_version, r.model, r.calls) for r in rows] == [
        (POSTING, "v1", "m", 1),
        (TAILOR, "v1", "m", 1),
        (TAILOR, "v1", "seed", 1),  # seeded rows never blend with real calls
        (TAILOR, "v2", "m", 1),
    ]
    by_key = {(r.feature, r.prompt_version, r.model): r for r in rows}
    assert by_key[(TAILOR, "v1", "m")].avg_edit_ratio == 0.0
    assert by_key[(TAILOR, "v2", "m")].avg_edit_ratio == pytest.approx(0.5)


def test_posting_analysis_rows_have_no_edit_ratio_no_edited_count_and_no_flags() -> None:
    calls = [call(i, POSTING) for i in range(1, 6)] + [call(6, POSTING, failed=True)]
    analyses = [
        analysis(1, 1, 1, APPROVED),
        analysis(2, 2, 2, REJECTED),
        analysis(3, 3, 3, DRAFT, day=0),  # superseded by the next one
        analysis(4, 3, 4, DRAFT, day=1),  # pending
        analysis(5, 4, 5, DRAFT),  # pending
    ]

    (row,) = ai_rows(calls, [], analyses)

    assert (row.calls, row.failed_calls) == (6, 1)
    assert (row.approved_as_is, row.rejected, row.pending, row.superseded) == (1, 1, 2, 1)
    assert row.edited_then_approved is None
    assert row.avg_edit_ratio is None
    assert row.avg_flags_per_draft is None


def test_a_group_with_no_approved_resume_has_no_edit_ratio() -> None:
    calls = [call(1)]
    resumes = [resume(1, 1, 1, REJECTED)]

    (row,) = ai_rows(calls, resumes, [])

    assert row.avg_edit_ratio is None
    assert row.avg_flags_per_draft == 0.0


def test_a_group_with_only_failed_calls_has_no_averages() -> None:
    (row,) = ai_rows([call(1, failed=True)], [], [])

    assert (row.calls, row.failed_calls) == (1, 1)
    assert (row.avg_edit_ratio, row.avg_flags_per_draft) == (None, None)
    assert (row.input_tokens, row.output_tokens, row.estimated_cost) == (0, 0, 0.0)


def test_no_calls_gives_no_rows() -> None:
    assert ai_rows([], [], []) == []


def test_flags_are_counted_as_generated() -> None:
    # The stored flags are the ones that count, whatever the text says now.
    calls = [call(1)]
    resumes = [resume(1, 1, 1, APPROVED, draft="abcd", content="completely different", flags=4)]

    (row,) = ai_rows(calls, resumes, [])

    assert row.avg_flags_per_draft == 4.0
