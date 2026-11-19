from app.core.clock import Clock, utc_now
from app.models import Resume, ReviewStatus
from app.repositories.resumes import BaseResumeExists, ResumeRepository


class ResumeNotFound(Exception):
    """No base resume has been saved yet."""


class ResumeService:
    def __init__(self, repository: ResumeRepository, clock: Clock = utc_now) -> None:
        self._repository = repository
        self._clock = clock

    def get_base(self) -> Resume:
        resume = self._repository.get_base()
        if resume is None:
            raise ResumeNotFound
        return resume

    def save_base(self, markdown: str) -> Resume:
        """Create the base resume, or replace its text in place. It is always approved: the
        user wrote it, so there is nothing to review. The text is stored exactly as given."""
        resume = self._repository.get_base()
        if resume is None:
            now = self._clock()
            try:
                resume = self._repository.add(
                    Resume(
                        content_markdown=markdown,
                        status=ReviewStatus.APPROVED,
                        created_at=now,
                        updated_at=now,
                    )
                )
            except BaseResumeExists:
                # A parallel save created it first, so replace that one.
                resume = self._repository.get_base()
            else:
                return self._finish(resume)
        resume.content_markdown = markdown
        resume.status = ReviewStatus.APPROVED
        resume.updated_at = self._clock()
        return self._finish(resume)

    def _finish(self, resume: Resume) -> Resume:
        self._repository.commit()
        self._repository.refresh(resume)
        return resume
