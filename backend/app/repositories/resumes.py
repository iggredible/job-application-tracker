from collections.abc import Collection

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, lazyload

from app.models import Resume, ReviewStatus


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

    def get_tailored_for_update(self, resume_id: int) -> Resume | None:
        """A tailored resume (made by an AI call for an application), locked until this
        transaction ends so an edit and a decision cannot both act on a stale status. The row
        is reloaded, so a change that committed while this one waited is seen. The base resume
        and base-resume snapshots are not tailored, so they are never returned."""
        query = (
            select(Resume)
            .where(
                Resume.id == resume_id,
                Resume.application_id.is_not(None),
                Resume.ai_call_id.is_not(None),
            )
            .with_for_update(of=Resume)
            .execution_options(populate_existing=True)
        )
        return self._session.scalar(query)

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

    def list_tailored(self) -> list[Resume]:
        """Every tailored resume (made by an AI call for an application), for the metrics. The
        base resume has no application and a base-resume snapshot has no AI call, so neither is
        listed. The AI call is not loaded: the metrics read the calls themselves."""
        query = (
            select(Resume)
            .where(Resume.application_id.is_not(None), Resume.ai_call_id.is_not(None))
            .options(lazyload(Resume.ai_call))
            .order_by(Resume.id)
        )
        return list(self._session.scalars(query))

    def add_snapshot(self, resume: Resume) -> Resume:
        """Insert a snapshot of the base resume (it belongs to an application and has no AI call)
        and flush so its id is available. The caller commits."""
        self._session.add(resume)
        self._session.flush()
        return resume

    def get_many(self, resume_ids: Collection[int]) -> dict[int, Resume]:
        if not resume_ids:
            return {}
        query = select(Resume).where(Resume.id.in_(resume_ids))
        return {resume.id: resume for resume in self._session.scalars(query)}

    def tailored_statuses_by_application(
        self, application_id: int | None = None
    ) -> dict[int, list[ReviewStatus]]:
        """The statuses of the tailored resumes (made by an AI call), newest first, by
        application: every application, or just `application_id`. A base-resume snapshot has no
        AI call, so it is never counted."""
        query = (
            select(Resume.application_id, Resume.status)
            .where(Resume.application_id.is_not(None), Resume.ai_call_id.is_not(None))
            .order_by(Resume.created_at.desc(), Resume.id.desc())
        )
        if application_id is not None:
            query = query.where(Resume.application_id == application_id)
        statuses: dict[int, list[ReviewStatus]] = {}
        for owner, status in self._session.execute(query):
            statuses.setdefault(owner, []).append(status)
        return statuses

    def commit(self) -> None:
        self._session.commit()

    def rollback(self) -> None:
        self._session.rollback()

    def refresh(self, resume: Resume) -> None:
        self._session.refresh(resume)
