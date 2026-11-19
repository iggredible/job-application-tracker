from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Resume


class BaseResumeExists(Exception):
    """The database already holds a base resume (unique index `resumes_one_base_idx`)."""


class ResumeRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_base(self) -> Resume | None:
        """The base resume is the one row that belongs to no application."""
        return self._session.scalar(select(Resume).where(Resume.application_id.is_(None)))

    def get(self, resume_id: int) -> Resume | None:
        return self._session.get(Resume, resume_id)

    def add(self, resume: Resume) -> Resume:
        """Raises BaseResumeExists when a second base resume would be created."""
        self._session.add(resume)
        try:
            self._session.flush()
        except IntegrityError:
            self._session.rollback()
            raise BaseResumeExists from None
        return resume

    def commit(self) -> None:
        self._session.commit()

    def refresh(self, resume: Resume) -> None:
        self._session.refresh(resume)
