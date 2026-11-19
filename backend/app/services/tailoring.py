from dataclasses import asdict

from app.ai.types import AIClient
from app.core.clock import Clock, utc_now
from app.models import AIFeature, Resume, ReviewStatus
from app.repositories.applications import ApplicationRepository
from app.repositories.locks import GenerationLockRepository
from app.repositories.posting_analyses import PostingAnalysisRepository
from app.repositories.resumes import ResumeRepository
from app.services.applications import ApplicationNotFound
from app.services.generation import tailor
from app.services.guardrail import check
from app.services.rendering import render_tailored_markdown
from app.services.resume_review import TailoredDraft, present
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

    def run(self, application_id: int, ai: AIClient) -> TailoredDraft:
        """Make one AI call and save the result as a draft tailored resume.

        The guards run first, so a refused request makes no call. The lock is held in this
        transaction until the draft is saved (or the call fails), so a second request for the
        same application is refused. A failed call saves nothing: the client has already logged
        it in its own transaction. The guardrail check runs on the output in this same call, and
        its flags are saved as generated.
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
            flags = check(result.output, base.content_markdown, analysis.keywords)
            now = self._clock()
            resume = self._resumes.add_draft(
                Resume(
                    application_id=application_id,
                    ai_call_id=result.ai_call_id,
                    content_json=result.output.model_dump(mode="json"),
                    draft_markdown=markdown,
                    content_markdown=markdown,
                    guardrail_flags=[asdict(flag) for flag in flags],
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
        # The new draft is the newest, so it is the first of the list, pending and displayed.
        return self.list_for_application(application_id)[0]

    def list_for_application(self, application_id: int) -> list[TailoredDraft]:
        """Newest first, each with its current flags, its outcome and whether it is displayed."""
        if self._applications.get(application_id) is None:
            raise ApplicationNotFound
        resumes = self._resumes.list_tailored_for_application(application_id)
        analysis = self._analyses.get_latest_approved(application_id)
        keywords = analysis.keywords if analysis else []
        return present(resumes, self._resumes.get_base(), keywords)
