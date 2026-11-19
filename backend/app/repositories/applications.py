from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Application, Stage


class ApplicationRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, application: Application) -> Application:
        self._session.add(application)
        self._session.flush()
        return application

    def get(self, application_id: int) -> Application | None:
        return self._session.get(Application, application_id)

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

    def update_stage(self, application: Application, stage: Stage) -> None:
        """The only place that writes `applications.stage`. Called only by change_stage()."""
        application.stage = stage
        self._session.flush()

    def commit(self) -> None:
        self._session.commit()

    def refresh(self, application: Application) -> None:
        self._session.refresh(application)
