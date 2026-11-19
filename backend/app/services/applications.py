# Deferred annotations: the `list` method below would otherwise shadow the builtin `list[...]`
# used in the annotations of later methods.
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.core.clock import Clock, utc_now
from app.models import Application, EventType, Stage, TimelineEvent
from app.repositories.applications import ApplicationRepository
from app.repositories.timeline import TimelineRepository
from app.schemas.application import ApplicationCreate, ApplicationUpdate
from app.services.staleness import idle_days, is_stale
from app.services.transitions import GuardContext, allowed_next, run_guards


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
        clock: Clock = utc_now,
    ) -> None:
        self._repository = repository
        self._timeline = timeline
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
        return self._view(application)

    def list(self, stage: Stage | None = None) -> ApplicationListing:
        """`stage` narrows the items only. Counts and the stale count cover everything."""
        applications = self._repository.list_all()
        last_activity = self._timeline.last_activity_by_application()
        views = {a.id: self._view(a, last_activity.get(a.id)) for a in applications}
        counts = self._repository.counts_by_stage()
        shown = applications if stage is None else self._repository.list_all(stage)
        return ApplicationListing(
            items=[views[a.id] for a in shown],
            counts_by_stage={s: counts.get(s, 0) for s in Stage},
            stale_count=sum(view.is_stale for view in views.values()),
        )

    def get(self, application_id: int) -> ApplicationView:
        return self._view(self._get(application_id))

    def update(self, application_id: int, data: ApplicationUpdate) -> ApplicationView:
        application = self._get(application_id)
        changes = data.model_dump(exclude_unset=True)
        if changes:
            for field, value in changes.items():
                setattr(application, field, value)
            self._repository.commit()
            self._repository.refresh(application)
        return self._view(application)

    def change_stage(
        self,
        application_id: int,
        to_stage: Stage,
        *,
        context: Mapping[str, Any] | None = None,
    ) -> ApplicationView:
        """The only way a stage changes. Validates the transition, runs the guards, updates the
        stage and writes the timeline event in one transaction."""
        application = self._get(application_id)
        current = application.stage

        allowed = allowed_next(current)
        if to_stage not in allowed:
            raise InvalidTransition(current, to_stage, allowed)
        guard_context = GuardContext(application=application, extra=context or {})
        failure = run_guards((current, to_stage), guard_context)
        if failure is not None:
            raise GuardFailed(failure.reason)

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
        self._repository.refresh(application)
        return self._view(application)

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

    def _view(
        self, application: Application, last_activity_at: datetime | None = None
    ) -> ApplicationView:
        # An application with no events falls back to its creation time.
        last = last_activity_at or self._timeline.last_activity(application.id)
        last = last or application.created_at
        now = self._clock()
        return ApplicationView(
            application=application,
            last_activity_at=last,
            allowed_next_stages=allowed_next(application.stage),
            is_stale=is_stale(application.stage, last, now),
            idle_days=idle_days(last, now),
        )
