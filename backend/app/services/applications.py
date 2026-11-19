# Deferred annotations: the `list` method below would otherwise shadow the builtin `list[...]`
# used in the annotations of later methods.
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.core.clock import Clock, utc_now
from app.models import Application, EventType, Resume, ReviewStatus, Stage, TimelineEvent
from app.repositories.applications import ApplicationRepository
from app.repositories.posting_analyses import PostingAnalysisRepository
from app.repositories.resumes import ResumeRepository
from app.repositories.timeline import TimelineRepository
from app.schemas.application import ApplicationCreate, ApplicationUpdate
from app.services.staleness import idle_days, is_stale
from app.services.submission import (
    SubmittableResume,
    SubmittedResume,
    WorkflowStep,
    submittable_options,
    submitted_resume_of,
    workflow_steps,
)
from app.services.transitions import (
    GuardContext,
    allowed_next,
    allowed_next_for_user,
    run_guards,
    stage_change_hint,
)


class ApplicationNotFound(Exception):
    """No application has the requested id."""


class InvalidTransition(Exception):
    def __init__(self, from_stage: Stage, to_stage: Stage, allowed: list[Stage]) -> None:
        self.from_stage = from_stage
        self.to_stage = to_stage
        self.allowed = allowed
        super().__init__(f"cannot move from {from_stage.value} to {to_stage.value}")


class GuardFailed(Exception):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


@dataclass(frozen=True)
class ApplicationView:
    """An application with the values calculated on request. None of them is stored."""

    application: Application
    last_activity_at: datetime
    allowed_next_stages: list[Stage]
    is_stale: bool
    idle_days: int
    submitted_resume: SubmittedResume | None
    applied_at: datetime | None
    stage_change_hint: str | None
    steps: list[WorkflowStep]


@dataclass(frozen=True)
class _Related:
    """What a view needs from other tables, read in a few queries for one application or all."""

    analyses: dict[int, list[ReviewStatus]]
    tailored: dict[int, list[ReviewStatus]]
    applied_at: dict[int, datetime]
    submitted: dict[int, Resume]
    has_base_resume: bool


@dataclass(frozen=True)
class ApplicationListing:
    items: list[ApplicationView]
    counts_by_stage: dict[Stage, int]
    stale_count: int


class ApplicationService:
    def __init__(
        self,
        repository: ApplicationRepository,
        timeline: TimelineRepository,
        resumes: ResumeRepository,
        analyses: PostingAnalysisRepository,
        clock: Clock = utc_now,
    ) -> None:
        self._repository = repository
        self._timeline = timeline
        self._resumes = resumes
        self._analyses = analyses
        self._clock = clock

    def create(self, data: ApplicationCreate) -> ApplicationView:
        # `stage` is not set: the column default `saved` applies. The initial event is
        # written in the same transaction.
        application = Application(**data.model_dump())
        self._repository.add(application)
        self._timeline.add(
            TimelineEvent(
                application_id=application.id,
                type=EventType.STAGE_CHANGE,
                from_stage=None,
                to_stage=Stage.SAVED,
                created_at=self._clock(),
            )
        )
        self._repository.commit()
        self._repository.refresh(application)
        return self._view(application, self._related([application], single=True))

    def list(self, stage: Stage | None = None) -> ApplicationListing:
        """`stage` narrows the items only. Counts and the stale count cover everything."""
        applications = self._repository.list_all()
        last_activity = self._timeline.last_activity_by_application()
        related = self._related(applications)
        views = {a.id: self._view(a, related, last_activity.get(a.id)) for a in applications}
        counts = self._repository.counts_by_stage()
        shown = applications if stage is None else self._repository.list_all(stage)
        return ApplicationListing(
            items=[views[a.id] for a in shown],
            counts_by_stage={s: counts.get(s, 0) for s in Stage},
            stale_count=sum(view.is_stale for view in views.values()),
        )

    def get(self, application_id: int) -> ApplicationView:
        application = self._get(application_id)
        return self._view(application, self._related([application], single=True))

    def update(self, application_id: int, data: ApplicationUpdate) -> ApplicationView:
        application = self._get(application_id)
        changes = data.model_dump(exclude_unset=True)
        if changes:
            for field, value in changes.items():
                setattr(application, field, value)
            self._repository.commit()
            self._repository.refresh(application)
        return self._view(application, self._related([application], single=True))

    def apply(
        self, application_id: int, choice: str | None, resume_id: int | None
    ) -> ApplicationView:
        """Saved -> Applied, with the resume the user sent: `choice` is "base" or "tailored" (and
        then `resume_id` is the tailored resume). The only caller that performs this move."""
        return self.change_stage(
            application_id, Stage.APPLIED, context={"choice": choice, "resume_id": resume_id}
        )

    def change_stage(
        self,
        application_id: int,
        to_stage: Stage,
        *,
        context: Mapping[str, Any] | None = None,
    ) -> ApplicationView:
        """The only way a stage changes. Validates the transition, runs the guards and the
        transition's effect, updates the stage and writes the timeline event in one transaction.
        The application row is locked meanwhile, so two requests cannot both move it. Any failure
        rolls back and releases the lock."""
        application = self._get_for_update(application_id)
        try:
            current = application.stage
            if to_stage not in allowed_next(current):
                raise InvalidTransition(current, to_stage, allowed_next_for_user(current))
            guard_context = self._guard_context(application, context or {})
            failure = run_guards((current, to_stage), guard_context)
            if failure is not None:
                raise GuardFailed(failure.reason)

            effect = _EFFECTS.get((current, to_stage))
            if effect is not None:
                effect(self, application, context or {})
            self._repository.update_stage(application, to_stage)
            self._timeline.add(
                TimelineEvent(
                    application_id=application.id,
                    type=EventType.STAGE_CHANGE,
                    from_stage=current,
                    to_stage=to_stage,
                    created_at=self._clock(),
                )
            )
            self._repository.commit()
        except Exception:
            self._repository.rollback()
            raise
        self._repository.refresh(application)
        return self._view(application, self._related([application], single=True))

    def submittable_resumes(self, application_id: int) -> list[SubmittableResume]:
        """The options for "Which resume did you send?": the application's tailored resumes
        (newest first), then the base resume when one exists."""
        self._get(application_id)
        tailored = self._resumes.list_tailored_for_application(application_id)
        return submittable_options(application_id, tailored, self._resumes.get_base())

    def _record_submitted_resume(
        self, application: Application, context: Mapping[str, Any]
    ) -> None:
        """The effect of Saved -> Applied, run after its guards pass. Sending the base resume
        saves a snapshot of it, so a later edit of the base resume cannot change what was sent;
        sending a tailored resume points at it (it is already read-only)."""
        if context["choice"] == "base":
            base = self._resumes.get_base()
            assert base is not None  # the guard checked
            now = self._clock()
            resume = self._resumes.add_snapshot(
                Resume(
                    application_id=application.id,
                    ai_call_id=None,
                    content_markdown=base.content_markdown,
                    status=ReviewStatus.APPROVED,
                    created_at=now,
                    updated_at=now,
                )
            )
        else:
            resume = self._resumes.get(context["resume_id"])
            assert resume is not None  # the guard checked
        self._repository.set_submitted_resume(application, resume.id)

    def _guard_context(self, application: Application, extra: Mapping[str, Any]) -> GuardContext:
        resume_id = extra.get("resume_id")
        chosen = self._resumes.get(resume_id) if isinstance(resume_id, int) else None
        return GuardContext(
            application=application,
            extra=extra,
            base_resume=self._resumes.get_base(),
            chosen_resume=chosen,
        )

    def add_note(self, application_id: int, note: str) -> TimelineEvent:
        self._get(application_id)
        event = self._timeline.add(
            TimelineEvent(
                application_id=application_id,
                type=EventType.NOTE,
                note=note,
                created_at=self._clock(),
            )
        )
        self._repository.commit()
        return event

    def timeline(self, application_id: int) -> list[TimelineEvent]:
        """Newest first."""
        self._get(application_id)
        return self._timeline.list_for_application(application_id)

    def _get(self, application_id: int) -> Application:
        application = self._repository.get(application_id)
        if application is None:
            raise ApplicationNotFound(application_id)
        return application

    def _get_for_update(self, application_id: int) -> Application:
        application = self._repository.get_for_update(application_id)
        if application is None:
            self._repository.rollback()
            raise ApplicationNotFound(application_id)
        return application

    def _related(self, applications: Sequence[Application], *, single: bool = False) -> _Related:
        """The other tables' part of a view, in a few queries however many applications there
        are. With `single`, `applications` is one application and the queries are narrowed to it."""
        only = applications[0].id if single else None
        submitted_ids = {a.submitted_resume_id for a in applications if a.submitted_resume_id}
        return _Related(
            analyses=self._analyses.statuses_by_application(only),
            tailored=self._resumes.tailored_statuses_by_application(only),
            applied_at=self._timeline.applied_at_by_application(only),
            submitted=self._resumes.get_many(submitted_ids),
            has_base_resume=self._resumes.get_base() is not None,
        )

    def _view(
        self,
        application: Application,
        related: _Related,
        last_activity_at: datetime | None = None,
    ) -> ApplicationView:
        # An application with no events falls back to its creation time.
        last = last_activity_at or self._timeline.last_activity(application.id)
        last = last or application.created_at
        now = self._clock()
        submitted = related.submitted.get(application.submitted_resume_id or 0)
        steps = workflow_steps(
            stage=application.stage,
            analysis_statuses=related.analyses.get(application.id, []),
            tailored_statuses=related.tailored.get(application.id, []),
            has_base_resume=related.has_base_resume,
            has_submitted_resume=application.submitted_resume_id is not None,
        )
        return ApplicationView(
            application=application,
            last_activity_at=last,
            allowed_next_stages=allowed_next_for_user(application.stage),
            is_stale=is_stale(application.stage, last, now),
            idle_days=idle_days(last, now),
            submitted_resume=submitted_resume_of(submitted) if submitted else None,
            applied_at=related.applied_at.get(application.id),
            stage_change_hint=stage_change_hint(application.stage),
            steps=steps,
        )


# What a transition does besides moving the stage and writing the event, run inside the same
# transaction after its guards pass. Data, like the guards: no `if` on a transition.
_EFFECTS = {
    (Stage.SAVED, Stage.APPLIED): ApplicationService._record_submitted_resume,
}
