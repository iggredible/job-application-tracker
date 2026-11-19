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

    def add_draft(self, resume: Resume) -> Resume:
        """Insert a tailored resume and flush so its id is available. The caller commits."""
        self._session.add(resume)
        self._session.flush()
        return resume

    def list_tailored_for_application(self, application_id: int) -> list[Resume]:
        """Tailored resumes (made by an AI call) of one application, newest first. The base
        resume has no application and a base-resume snapshot has no AI call, so neither is
        listed."""
        query = (
            select(Resume)
            .where(Resume.application_id == application_id, Resume.ai_call_id.is_not(None))
            .order_by(Resume.created_at.desc(), Resume.id.desc())
        )
        return list(self._session.scalars(query))

    def commit(self) -> None:
        self._session.commit()

    def rollback(self) -> None:
        self._session.rollback()

    def refresh(self, resume: Resume) -> None:
        self._session.refresh(resume)
