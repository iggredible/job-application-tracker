from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Application


class ApplicationRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, application: Application) -> Application:
        self._session.add(application)
        self._session.flush()
        return application

    def get(self, application_id: int) -> Application | None:
        return self._session.get(Application, application_id)

    def list_all(self) -> list[Application]:
        """Newest first."""
        query = select(Application).order_by(Application.created_at.desc(), Application.id.desc())
        return list(self._session.scalars(query))

    def commit(self) -> None:
        self._session.commit()

    def refresh(self, application: Application) -> None:
        self._session.refresh(application)
