"""Process and AI metrics. Every number is calculated on request from the event logs and the
rows they produced, and none is stored.

The pure functions take rows and return numbers, so they are tested on small hand-built datasets.
`MetricsService` only fetches the rows and puts the results together. It reuses the rules that
already exist: `derive_outcome()` and `edit_ratio()` (feature 10), `is_stale()` (feature 3),
`resume_kind()` (feature 11) and `allowed_next()`.
"""

import statistics
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.core.clock import Clock, utc_now
from app.models import AIFeature, PostingAnalysis, Resume, ReviewStatus, Stage
from app.repositories.ai_calls import AICallRepository, AICallRow
from app.repositories.applications import ApplicationRepository, ApplicationSummary
from app.repositories.posting_analyses import PostingAnalysisRepository
from app.repositories.resumes import ResumeRepository
from app.repositories.timeline import StageChange, TimelineRepository
from app.services.resume_review import Outcome, derive_outcome, edit_ratio
from app.services.staleness import is_stale
from app.services.submission import ResumeKind, resume_kind
from app.services.transitions import allowed_next

S = Stage

# The funnel, in order. Reaching a later stage counts as having passed the earlier ones, so an
# application that went from Applied straight to Interviewing still counts at Screening.
FUNNEL: tuple[Stage, ...] = (S.APPLIED, S.SCREENING, S.INTERVIEWING, S.OFFER)
# Stages that are not in the funnel but count as having reached one of its stages.
COUNTS_AS: dict[Stage, Stage] = {S.ACCEPTED: S.OFFER}

# Features whose output the user edits before approving it. The others have no edit ratio, no
# "edited, then approved" count and no guardrail flags.
EDITABLE: frozenset[AIFeature] = frozenset({AIFeature.TAILOR_RESUME})

SECONDS_PER_DAY = 86_400


def _rate(part: int, whole: int) -> float | None:
    return part / whole if whole else None


def _utc(moment: datetime) -> datetime:
    """The same moment in UTC. Two datetimes that share one tzinfo are compared and subtracted by
    their wall-clock time, so across a daylight-saving change a gap of 14 days would be 14 days
    less an hour. Converting first makes both exact."""
    return moment.astimezone(UTC)


def _by_application(changes: Iterable[StageChange]) -> dict[int, list[StageChange]]:
    """Each application's stage changes, oldest first. The order given breaks ties."""
    grouped: dict[int, list[StageChange]] = defaultdict(list)
    for change in changes:
        grouped[change.application_id].append(change)
    return {
        key: sorted(events, key=lambda event: _utc(event.at)) for key, events in grouped.items()
    }


def _funnel_index(stage: Stage) -> int | None:
    """Where `stage` falls in the funnel, or None when it is not part of it."""
    stage = COUNTS_AS.get(stage, stage)
    return FUNNEL.index(stage) if stage in FUNNEL else None


# --- process metrics ----------------------------------------------------------------------------


@dataclass(frozen=True)
class FunnelCount:
    stage: Stage
    count: int
    share_of_previous: float | None  # None for the first stage, or when the step before is empty


def funnel(changes: Sequence[StageChange]) -> list[FunnelCount]:
    """How many applications reached each funnel stage, read from the timeline and not from the
    current stage, and the share that moved on from the stage before."""
    furthest = []
    for events in _by_application(changes).values():
        indexes = [i for e in events if (i := _funnel_index(e.to_stage)) is not None]
        if indexes:
            furthest.append(max(indexes))
    counts = [sum(1 for reached in furthest if reached >= i) for i in range(len(FUNNEL))]
    return [
        FunnelCount(stage, count, _rate(count, counts[i - 1]) if i else None)
        for i, (stage, count) in enumerate(zip(FUNNEL, counts, strict=True))
    ]


def applied_ids(changes: Sequence[StageChange]) -> set[int]:
    """The applications that reached Applied (or a stage after it)."""
    return {
        application_id
        for application_id, events in _by_application(changes).items()
        if any(_funnel_index(event.to_stage) is not None for event in events)
    }


def responded_ids(changes: Sequence[StageChange]) -> set[int]:
    """The applied applications with any later stage change other than Withdrawn. A rejection is
    a response; withdrawing is not."""
    responded = set()
    for application_id, events in _by_application(changes).items():
        applied = next(
            (i for i, e in enumerate(events) if _funnel_index(e.to_stage) is not None), None
        )
        if applied is not None and any(
            e.to_stage is not S.WITHDRAWN for e in events[applied + 1 :]
        ):
            responded.add(application_id)
    return responded


@dataclass(frozen=True)
class StageTime:
    stage: Stage
    median_days: float | None
    sample_size: int


def time_in_stage(changes: Sequence[StageChange]) -> list[StageTime]:
    """Median days spent in each stage that can be left, from completed intervals only.

    An interval runs from entering a stage to the next stage change. The stage an application is
    still in has no next change, and a terminal stage never does, so neither is counted.
    """
    durations: dict[Stage, list[float]] = {stage: [] for stage in Stage if allowed_next(stage)}
    for events in _by_application(changes).values():
        for entered, left in zip(events, events[1:], strict=False):
            if entered.to_stage in durations:
                days = (_utc(left.at) - _utc(entered.at)) / timedelta(days=1)
                durations[entered.to_stage].append(days)
    return [
        StageTime(stage, statistics.median(days) if days else None, len(days))
        for stage, days in durations.items()
    ]


@dataclass(frozen=True)
class ResponseCount:
    applied: int
    responses: int
    rate: float | None


@dataclass(frozen=True)
class ResumeComparison:
    tailored: ResponseCount
    base: ResponseCount


@dataclass(frozen=True)
class PipelineResult:
    total_applications: int
    applied_applications: int
    funnel: list[FunnelCount]
    time_in_stage: list[StageTime]
    response: ResponseCount
    stale_applications: int
    resume_comparison: ResumeComparison


# --- AI metrics ---------------------------------------------------------------------------------


@dataclass(frozen=True)
class AIRow:
    feature: AIFeature
    prompt_version: str
    model: str
    calls: int
    failed_calls: int
    approved_as_is: int
    edited_then_approved: int | None
    rejected: int
    pending: int
    superseded: int
    avg_edit_ratio: float | None
    avg_flags_per_draft: float | None
    input_tokens: int
    output_tokens: int
    estimated_cost: float
    median_latency_ms: float


@dataclass(frozen=True)
class _Artifact:
    """What a call produced, with what the metrics need from it."""

    call_id: int
    outcome: Outcome
    edit_ratio: float | None  # of an approved tailored resume; None otherwise
    flags: int | None  # the flags as generated; None for an analysis


def _outcomes(
    items: Sequence[Resume | PostingAnalysis],
) -> list[tuple[Resume | PostingAnalysis, Outcome]]:
    """The outcome of each item. Within an application, a draft is superseded when a newer one
    exists, the same rule the review flow uses. A decided item is never superseded."""
    by_application: dict[int, list[Resume | PostingAnalysis]] = defaultdict(list)
    for item in items:
        by_application[item.application_id].append(item)
    result = []
    for siblings in by_application.values():
        newest_first = sorted(siblings, key=lambda item: (item.created_at, item.id), reverse=True)
        for position, item in enumerate(newest_first):
            # An analysis has no text to edit: the same text on both sides means "as generated".
            draft, content = (
                (item.draft_markdown, item.content_markdown)
                if isinstance(item, Resume)
                else ("", "")
            )
            result.append((item, derive_outcome(item.status, draft, content, position > 0)))
    return result


def _artifacts(resumes: Sequence[Resume], analyses: Sequence[PostingAnalysis]) -> list[_Artifact]:
    artifacts = []
    for item, outcome in _outcomes(resumes) + _outcomes(analyses):
        if isinstance(item, Resume):
            ratio = (
                edit_ratio(item.draft_markdown or "", item.content_markdown)
                if item.status is ReviewStatus.APPROVED
                else None
            )
            artifacts.append(
                _Artifact(item.ai_call_id or 0, outcome, ratio, len(item.guardrail_flags))
            )
        else:
            artifacts.append(_Artifact(item.ai_call_id, outcome, None, None))
    return artifacts


def _mean(values: Sequence[float]) -> float | None:
    return statistics.fmean(values) if values else None


def ai_rows(
    calls: Sequence[AICallRow], resumes: Sequence[Resume], analyses: Sequence[PostingAnalysis]
) -> list[AIRow]:
    """One row per feature, prompt version and model, so seeded calls (model `seed`) never blend
    with real ones. `resumes` must be the tailored ones: a snapshot of the base resume was not
    made by a call and is not an AI output.

    Outcome counts come from the artifacts the calls produced. A failed call produced none, so
    it is in `calls` and `failed_calls` only.
    """
    groups: dict[tuple[AIFeature, str, str], list[AICallRow]] = defaultdict(list)
    key_of_call: dict[int, tuple[AIFeature, str, str]] = {}
    for call in calls:
        key = (call.feature, call.prompt_version, call.model)
        groups[key].append(call)
        key_of_call[call.id] = key

    produced: dict[tuple[AIFeature, str, str], list[_Artifact]] = defaultdict(list)
    for artifact in _artifacts(resumes, analyses):
        if artifact.call_id in key_of_call:
            produced[key_of_call[artifact.call_id]].append(artifact)

    rows = []
    for key in sorted(groups, key=lambda k: (list(AIFeature).index(k[0]), k[1], k[2])):
        feature, prompt_version, model = key
        group, artifacts = groups[key], produced[key]
        counts = {outcome: sum(a.outcome is outcome for a in artifacts) for outcome in Outcome}
        editable = feature in EDITABLE
        rows.append(
            AIRow(
                feature=feature,
                prompt_version=prompt_version,
                model=model,
                calls=len(group),
                failed_calls=sum(call.error is not None for call in group),
                approved_as_is=counts[Outcome.APPROVED],
                edited_then_approved=counts[Outcome.EDITED_THEN_APPROVED] if editable else None,
                rejected=counts[Outcome.REJECTED],
                pending=counts[Outcome.PENDING],
                superseded=counts[Outcome.SUPERSEDED],
                avg_edit_ratio=(
                    _mean([a.edit_ratio for a in artifacts if a.edit_ratio is not None])
                    if editable
                    else None
                ),
                avg_flags_per_draft=(
                    _mean([a.flags for a in artifacts if a.flags is not None]) if editable else None
                ),
                input_tokens=sum(call.input_tokens or 0 for call in group),
                output_tokens=sum(call.output_tokens or 0 for call in group),
                estimated_cost=float(sum(call.estimated_cost or 0 for call in group)),
                median_latency_ms=float(statistics.median(call.latency_ms for call in group)),
            )
        )
    return rows


@dataclass(frozen=True)
class AIResult:
    rows: list[AIRow]


# --- the service --------------------------------------------------------------------------------


class MetricsService:
    """Reads only. Nothing here writes a row."""

    def __init__(
        self,
        applications: ApplicationRepository,
        timeline: TimelineRepository,
        resumes: ResumeRepository,
        analyses: PostingAnalysisRepository,
        ai_calls: AICallRepository,
        clock: Clock = utc_now,
    ) -> None:
        self._applications = applications
        self._timeline = timeline
        self._resumes = resumes
        self._analyses = analyses
        self._ai_calls = ai_calls
        self._clock = clock

    def pipeline(self) -> PipelineResult:
        changes = self._timeline.stage_changes()
        applied = applied_ids(changes)
        responded = responded_ids(changes)
        summaries = self._applications.summaries()
        return PipelineResult(
            total_applications=len(summaries),
            applied_applications=len(applied),
            funnel=funnel(changes),
            time_in_stage=time_in_stage(changes),
            response=ResponseCount(
                len(applied), len(responded), _rate(len(responded), len(applied))
            ),
            stale_applications=self._stale_count(summaries),
            resume_comparison=self._compare_resumes(summaries, applied, responded),
        )

    def ai(self) -> AIResult:
        return AIResult(
            ai_rows(
                self._ai_calls.list_for_metrics(),
                self._resumes.list_tailored(),
                self._analyses.list_all(),
            )
        )

    def _stale_count(self, summaries: Sequence[ApplicationSummary]) -> int:
        """The feature 3 rule, on the current stage and the last timeline activity (an
        application with no events falls back to its creation time)."""
        last_activity = self._timeline.last_activity_by_application()
        now = self._clock()
        return sum(is_stale(s.stage, last_activity.get(s.id, s.created_at), now) for s in summaries)

    def _compare_resumes(
        self, summaries: Sequence[ApplicationSummary], applied: set[int], responded: set[int]
    ) -> ResumeComparison:
        """Response rate by the kind of resume sent. A snapshot of the base resume counts as
        base. An applied application with no submitted resume is in neither group."""
        submitted = {s.id: s.submitted_resume_id for s in summaries if s.id in applied}
        resumes = self._resumes.get_many({rid for rid in submitted.values() if rid is not None})
        totals = {kind: [0, 0] for kind in ResumeKind}  # [applied, responses]
        for application_id, resume_id in submitted.items():
            resume = resumes.get(resume_id) if resume_id is not None else None
            if resume is None:
                continue
            kind = resume_kind(resume)
            totals[kind][0] += 1
            totals[kind][1] += application_id in responded

        def count(kind: ResumeKind) -> ResponseCount:
            applied_count, responses = totals[kind]
            return ResponseCount(applied_count, responses, _rate(responses, applied_count))

        return ResumeComparison(tailored=count(ResumeKind.TAILORED), base=count(ResumeKind.BASE))
