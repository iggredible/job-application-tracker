from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Application, Stage


@dataclass(frozen=True)
class ApplicationSummary:
    """What the metrics read from an application: no posting text, no company."""

    id: int
    stage: Stage
    created_at: datetime
    submitted_resume_id: int | None


class ApplicationRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, application: Application) -> Application:
        self._session.add(application)
        self._session.flush()
        return application

    def get(self, application_id: int) -> Application | None:
        return self._session.get(Application, application_id)

    def get_for_update(self, application_id: int) -> Application | None:
        """Read the row and lock it until this transaction ends, so two requests to move the
        same application cannot both act on a stale stage. The row is reloaded, so a change that
        committed while this one waited is seen."""
        query = (
            select(Application)
            .where(Application.id == application_id)
            .with_for_update(of=Application)
            .execution_options(populate_existing=True)
        )
        return self._session.scalar(query)

    def list_all(self, stage: Stage | None = None) -> list[Application]:
        """Newest first, optionally only one stage."""
        query = select(Application).order_by(Application.created_at.desc(), Application.id.desc())
        if stage is not None:
            query = query.where(Application.stage == stage)
        return list(self._session.scalars(query))

    def counts_by_stage(self) -> dict[Stage, int]:
        """Only stages that have applications appear in the result."""
        query = select(Application.stage, func.count()).group_by(Application.stage)
        return {stage: count for stage, count in self._session.execute(query)}

    def summaries(self) -> list[ApplicationSummary]:
        """Every application, reduced to the columns the metrics need."""
        query = select(
            Application.id,
            Application.stage,
            Application.created_at,
            Application.submitted_resume_id,
        ).order_by(Application.id)
        return [ApplicationSummary(*row) for row in self._session.execute(query)]

    def update_stage(self, application: Application, stage: Stage) -> None:
        """The only place that writes `applications.stage`. Called only by change_stage()."""
        application.stage = stage
        self._session.flush()

    def set_submitted_resume(self, application: Application, resume_id: int) -> None:
        """The only place that writes `applications.submitted_resume_id`. Called only when the
        application moves Saved -> Applied, so it never changes after that."""
        application.submitted_resume_id = resume_id
        self._session.flush()

    def commit(self) -> None:
        self._session.commit()

    def rollback(self) -> None:
        self._session.rollback()

    def refresh(self, application: Application) -> None:
        self._session.refresh(application)
