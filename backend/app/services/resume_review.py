"""Reviewing a tailored resume: edit the draft, then approve or reject it.

The outcome, the edit ratio and which resume is displayed are calculated on request from the
stored rows and never stored. A status is set only by `review.apply_decision()`, and
`draft_markdown` is never written after the resume is created.
"""

import enum
from collections.abc import Sequence
from dataclasses import dataclass
from difflib import SequenceMatcher

from app.core.clock import Clock, utc_now
from app.models import Resume, ReviewStatus
from app.repositories.posting_analyses import PostingAnalysisRepository
from app.repositories.resumes import ResumeRepository
from app.services.coverage import ApplicationCoverage, CoverageService
from app.services.guardrail import Flag, current_flags
from app.services.review import NotReviewable, apply_decision


class TailoredResumeNotFound(Exception):
    """No tailored resume has this id (the base resume and its snapshots are not tailored)."""


class NotEditable(Exception):
    """Only a draft can be edited."""


class Outcome(enum.Enum):
    """What became of a tailored resume. Derived on request, never stored."""

    PENDING = "pending"
    SUPERSEDED = "superseded"
    APPROVED = "approved"
    EDITED_THEN_APPROVED = "edited_then_approved"
    REJECTED = "rejected"


def derive_outcome(
    status: ReviewStatus, draft_markdown: str | None, content_markdown: str, superseded: bool
) -> Outcome:
    """A draft is pending, or superseded when a newer draft exists for the same application. An
    approved resume is edited when its text differs from the text as generated. A newer draft
    never changes a decided resume."""
    if status is ReviewStatus.REJECTED:
        return Outcome.REJECTED
    if status is ReviewStatus.APPROVED:
        edited = content_markdown != draft_markdown
        return Outcome.EDITED_THEN_APPROVED if edited else Outcome.APPROVED
    return Outcome.SUPERSEDED if superseded else Outcome.PENDING


def edit_ratio(draft_markdown: str, content_markdown: str) -> float:
    """How much the user changed the draft: 0 means unedited, 1 means nothing is left. The AI
    metrics (feature 14) average it over the approved drafts."""
    matcher = SequenceMatcher(None, draft_markdown, content_markdown, autojunk=False)
    return 1 - matcher.ratio()


def displayed_resume(resumes: Sequence[Resume]) -> Resume | None:
    """The resume the Tailored resume section shows. `resumes` is newest first.

    The newest one if it is a draft awaiting review; otherwise the latest approved; otherwise
    the latest rejected.
    """
    if not resumes:
        return None
    if resumes[0].status is ReviewStatus.DRAFT:
        return resumes[0]
    for wanted in (ReviewStatus.APPROVED, ReviewStatus.REJECTED):
        for resume in resumes:
            if resume.status is wanted:
                return resume
    return None  # unreachable: the newest is not a draft, so it is approved or rejected


@dataclass(frozen=True)
class TailoredDraft:
    """A tailored resume with what to show beside it: the current guardrail flags (not the
    stored ones), its outcome and whether it is the one the section displays."""

    resume: Resume
    flags: list[Flag]
    outcome: Outcome
    displayed: bool


def present(
    resumes: Sequence[Resume], base: Resume | None, keywords: list[str]
) -> list[TailoredDraft]:
    """The tailored resumes of one application, newest first (as given), each with its current
    flags, its outcome and whether it is displayed.

    The flags follow the text as it is now, the current base resume and the keywords of the
    latest approved analysis. The flags as generated stay in `guardrail_flags`. A resume is
    superseded when a newer one exists: every resume but the first.
    """
    shown = displayed_resume(resumes)
    drafts = []
    for position, resume in enumerate(resumes):
        stored = [Flag(**flag) for flag in resume.guardrail_flags]
        flags = (
            stored
            if base is None
            else current_flags(stored, resume.content_markdown, base.content_markdown, keywords)
        )
        outcome = derive_outcome(
            resume.status, resume.draft_markdown, resume.content_markdown, position > 0
        )
        drafts.append(TailoredDraft(resume, flags, outcome, resume is shown))
    return drafts


@dataclass(frozen=True)
class SavedEdit:
    """The draft after an edit, and the coverage of its new text against the base resume."""

    draft: TailoredDraft
    coverage: ApplicationCoverage


class TailoredReviewService:
    def __init__(
        self,
        resumes: ResumeRepository,
        analyses: PostingAnalysisRepository,
        coverage: CoverageService,
        clock: Clock = utc_now,
    ) -> None:
        self._resumes = resumes
        self._analyses = analyses
        self._coverage = coverage
        self._clock = clock

    def save_edits(self, resume_id: int, markdown: str) -> SavedEdit:
        """Replace the text of a draft, exactly as given. Only `content_markdown` changes: the
        text as generated and the flags as generated stay as they were."""
        resume = self._lock(resume_id)
        if resume.status is not ReviewStatus.DRAFT:
            self._resumes.rollback()  # release the row lock
            raise NotEditable("only a draft can be edited")
        resume.content_markdown = markdown
        resume.updated_at = self._clock()
        self._resumes.commit()
        self._resumes.refresh(resume)
        draft = self._present(resume)
        coverage = self._coverage.for_application(resume.application_id, resume.id)  # type: ignore[arg-type]
        return SavedEdit(draft, coverage)

    def approve(self, resume_id: int) -> TailoredDraft:
        return self._decide(resume_id, ReviewStatus.APPROVED)

    def reject(self, resume_id: int) -> TailoredDraft:
        return self._decide(resume_id, ReviewStatus.REJECTED)

    def _decide(self, resume_id: int, decision: ReviewStatus) -> TailoredDraft:
        resume = self._lock(resume_id)
        try:
            apply_decision(resume, decision, self._clock())  # raises NotReviewable
        except NotReviewable:
            self._resumes.rollback()  # release the row lock
            raise
        self._resumes.commit()
        self._resumes.refresh(resume)
        return self._present(resume)

    def _lock(self, resume_id: int) -> Resume:
        resume = self._resumes.get_tailored_for_update(resume_id)
        if resume is None:
            self._resumes.rollback()
            raise TailoredResumeNotFound
        return resume

    def _present(self, resume: Resume) -> TailoredDraft:
        """This resume as the list would show it, now that the change is saved."""
        application_id = resume.application_id
        siblings = self._resumes.list_tailored_for_application(application_id)  # type: ignore[arg-type]
        analysis = self._analyses.get_latest_approved(application_id)  # type: ignore[arg-type]
        keywords = analysis.keywords if analysis else []
        drafts = present(siblings, self._resumes.get_base(), keywords)
        return next(draft for draft in drafts if draft.resume.id == resume.id)
