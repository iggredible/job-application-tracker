from dataclasses import dataclass

from app.ai.types import AIClient
from app.core.clock import Clock, utc_now
from app.models import AIFeature, PostingAnalysis, ReviewStatus
from app.repositories.applications import ApplicationRepository
from app.repositories.locks import GenerationLockRepository
from app.repositories.posting_analyses import PostingAnalysisRepository
from app.services.applications import ApplicationNotFound
from app.services.generation import analyze
from app.services.review import NotReviewable, apply_decision


class AnalysisNotFound(Exception):
    """No posting analysis has this id."""


class AnalysisInProgress(Exception):
    """An analysis for this application is already running."""


@dataclass(frozen=True)
class AnalysisView:
    """An analysis and the prompt version that produced it (read from its AI call)."""

    analysis: PostingAnalysis
    prompt_version: str


class PostingAnalysisService:
    def __init__(
        self,
        analyses: PostingAnalysisRepository,
        applications: ApplicationRepository,
        locks: GenerationLockRepository,
        clock: Clock = utc_now,
    ) -> None:
        self._analyses = analyses
        self._applications = applications
        self._locks = locks
        self._clock = clock

    def run(self, application_id: int, ai: AIClient) -> AnalysisView:
        """Make one AI call for the application's posting and save the result as a draft.

        The lock is held in this transaction until the result is saved (or the call fails), so a
        second request for the same application is refused instead of making a second call. A
        failed call saves nothing: the client has already logged it in its own transaction.
        """
        application = self._applications.get(application_id)
        if application is None:
            raise ApplicationNotFound
        if not self._locks.try_lock(AIFeature.POSTING_ANALYSIS, application_id):
            self._analyses.rollback()
            raise AnalysisInProgress

        try:
            result = analyze(
                ai, posting_text=application.posting_text, application_id=application_id
            )
            analysis = self._analyses.add(
                PostingAnalysis(
                    application_id=application_id,
                    ai_call_id=result.ai_call_id,
                    requirements=[
                        {"text": r.text, "category": r.category.value}
                        for r in result.output.requirements
                    ],
                    keywords=result.output.keywords,
                    created_at=self._clock(),
                )
            )
            self._analyses.commit()
        except Exception:
            self._analyses.rollback()  # also releases the lock
            raise
        self._analyses.refresh(analysis)
        return _view(analysis)

    def get_for_display(self, application_id: int) -> AnalysisView | None:
        """The most recent analysis, except that a rejected one never hides an older approved
        one. When the newest is rejected and nothing is approved, the rejected one is shown."""
        if self._applications.get(application_id) is None:
            raise ApplicationNotFound
        analyses = self._analyses.list_for_application(application_id)
        if not analyses:
            return None
        newest = analyses[0]
        if newest.status is ReviewStatus.REJECTED:
            approved = next((a for a in analyses if a.status is ReviewStatus.APPROVED), None)
            return _view(approved or newest)
        return _view(newest)

    def approve(self, analysis_id: int) -> AnalysisView:
        return self._decide(analysis_id, ReviewStatus.APPROVED)

    def reject(self, analysis_id: int) -> AnalysisView:
        return self._decide(analysis_id, ReviewStatus.REJECTED)

    def _decide(self, analysis_id: int, decision: ReviewStatus) -> AnalysisView:
        # Locked, so two decisions on the same analysis cannot both see a draft.
        analysis = self._analyses.get_for_update(analysis_id)
        if analysis is None:
            raise AnalysisNotFound
        try:
            apply_decision(analysis, decision, self._clock())  # raises NotReviewable
        except NotReviewable:
            self._analyses.rollback()  # release the row lock
            raise
        self._analyses.commit()
        self._analyses.refresh(analysis)
        return _view(analysis)


def _view(analysis: PostingAnalysis) -> AnalysisView:
    return AnalysisView(analysis=analysis, prompt_version=analysis.ai_call.prompt_version)
