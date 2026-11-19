from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import EventType, Stage, TimelineEvent


@dataclass(frozen=True)
class StageChange:
    """An application moved to `to_stage` at `at`. The metrics read the timeline through these."""

    application_id: int
    from_stage: Stage | None
    to_stage: Stage
    at: datetime


class TimelineRepository:
    """Append-only: there is deliberately no update or delete here."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, event: TimelineEvent) -> TimelineEvent:
        self._session.add(event)
        self._session.flush()
        return event

    def list_for_application(self, application_id: int) -> list[TimelineEvent]:
        """Newest first. The id breaks ties between events with the same timestamp."""
        query = (
            select(TimelineEvent)
            .where(TimelineEvent.application_id == application_id)
            .order_by(TimelineEvent.created_at.desc(), TimelineEvent.id.desc())
        )
        return list(self._session.scalars(query))

    def last_activity(self, application_id: int) -> datetime | None:
        query = select(func.max(TimelineEvent.created_at)).where(
            TimelineEvent.application_id == application_id
        )
        return self._session.scalar(query)

    def applied_at_by_application(self, application_id: int | None = None) -> dict[int, datetime]:
        """When each application moved Saved -> Applied (an application moves there once), for
        every application or just `application_id`. Applications that never did are absent."""
        query = select(TimelineEvent.application_id, func.min(TimelineEvent.created_at)).where(
            TimelineEvent.type == EventType.STAGE_CHANGE,
            TimelineEvent.from_stage == Stage.SAVED,
            TimelineEvent.to_stage == Stage.APPLIED,
        )
        if application_id is not None:
            query = query.where(TimelineEvent.application_id == application_id)
        query = query.group_by(TimelineEvent.application_id)
        return {owner: applied_at for owner, applied_at in self._session.execute(query)}

    def stage_changes(self) -> list[StageChange]:
        """Every stage change of every application, oldest first. Notes are not included."""
        query = (
            select(
                TimelineEvent.application_id,
                TimelineEvent.from_stage,
                TimelineEvent.to_stage,
                TimelineEvent.created_at,
            )
            .where(TimelineEvent.type == EventType.STAGE_CHANGE)
            .order_by(TimelineEvent.created_at, TimelineEvent.id)
        )
        return [StageChange(*row) for row in self._session.execute(query)]

    def last_activity_by_application(self) -> dict[int, datetime]:
        query = select(TimelineEvent.application_id, func.max(TimelineEvent.created_at)).group_by(
            TimelineEvent.application_id
        )
        return {application_id: last for application_id, last in self._session.execute(query)}
