from app.ai.types import AIClient
from app.core.clock import Clock, utc_now
from app.models import AIFeature, Resume, ReviewStatus
from app.repositories.applications import ApplicationRepository
from app.repositories.locks import GenerationLockRepository
from app.repositories.posting_analyses import PostingAnalysisRepository
from app.repositories.resumes import ResumeRepository
from app.services.applications import ApplicationNotFound
from app.services.generation import tailor
from app.services.rendering import render_tailored_markdown
from app.services.transitions import GuardContext, run_guards


class TailoringBlocked(Exception):
    """A guard refused to start a tailoring. `reason` says why."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class TailoringInProgress(Exception):
    """A tailoring for this application is already running."""


class TailoredResumeService:
    def __init__(
        self,
        resumes: ResumeRepository,
        analyses: PostingAnalysisRepository,
        applications: ApplicationRepository,
        locks: GenerationLockRepository,
        clock: Clock = utc_now,
    ) -> None:
        self._resumes = resumes
        self._analyses = analyses
        self._applications = applications
        self._locks = locks
        self._clock = clock

    def run(self, application_id: int, ai: AIClient) -> Resume:
        """Make one AI call and save the result as a draft tailored resume.

        The guards run first, so a refused request makes no call. The lock is held in this
        transaction until the draft is saved (or the call fails), so a second request for the
        same application is refused. A failed call saves nothing: the client has already logged
        it in its own transaction.
        """
        application = self._applications.get(application_id)
        if application is None:
            raise ApplicationNotFound
        analysis = self._analyses.get_latest_approved(application_id)
        base = self._resumes.get_base()
        failure = run_guards(
            "start_tailoring",
            GuardContext(application=application, approved_analysis=analysis, base_resume=base),
        )
        if failure is not None:
            self._resumes.rollback()
            raise TailoringBlocked(failure.reason)
        if not self._locks.try_lock(AIFeature.TAILOR_RESUME, application_id):
            self._resumes.rollback()
            raise TailoringInProgress

        try:
            result = tailor(
                ai,
                base_resume=base.content_markdown,
                posting_text=application.posting_text,
                keywords=analysis.keywords,
                application_id=application_id,
            )
            markdown = render_tailored_markdown(base.content_markdown, result.output)
            now = self._clock()
            resume = self._resumes.add_draft(
                Resume(
                    application_id=application_id,
                    ai_call_id=result.ai_call_id,
                    content_json=result.output.model_dump(mode="json"),
                    draft_markdown=markdown,
                    content_markdown=markdown,
                    status=ReviewStatus.DRAFT,
                    created_at=now,
                    updated_at=now,
                )
            )
            self._resumes.commit()
        except Exception:
            self._resumes.rollback()  # also releases the lock
            raise
        self._resumes.refresh(resume)
        return resume

    def list_for_application(self, application_id: int) -> list[Resume]:
        """Newest first."""
        if self._applications.get(application_id) is None:
            raise ApplicationNotFound
        return self._resumes.list_tailored_for_application(application_id)
