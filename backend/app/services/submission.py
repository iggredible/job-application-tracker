"""Which resume an application sent, and the three workflow steps. Pure: nothing here reads the
database or the clock, and nothing it returns is stored.

The steps are posting analysis, tailored resume and mark as applied. Their status is calculated
on every request from the stage and the related records, so the frontend holds no step logic.
"""

import enum
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from app.models import Resume, ReviewStatus, Stage

# --- which resume was sent ----------------------------------------------------------------------


class ResumeKind(enum.Enum):
    BASE = "base"  # the base resume, or the snapshot saved when it was sent
    TAILORED = "tailored"


def resume_kind(resume: Resume) -> ResumeKind:
    """A tailored resume was made by an AI call. The base resume and a snapshot of it were not."""
    return ResumeKind.TAILORED if resume.ai_call_id is not None else ResumeKind.BASE


@dataclass(frozen=True)
class SubmittedResume:
    id: int
    kind: ResumeKind
    created_at: datetime


def submitted_resume_of(resume: Resume) -> SubmittedResume:
    return SubmittedResume(resume.id, resume_kind(resume), resume.created_at)


def unsubmittable_reason(resume: Resume, application_id: int) -> str | None:
    """Why this resume cannot be sent as the tailored resume of `application_id`, or None when
    it can: it must be a tailored resume of this application and approved. The base resume and
    its snapshots are not tailored, so they are never accepted here."""
    if resume.ai_call_id is None:
        return "That is not a tailored resume"
    if resume.application_id != application_id:
        return "That resume belongs to another application"
    if resume.status is ReviewStatus.DRAFT:
        return "Approve this draft first"
    if resume.status is ReviewStatus.REJECTED:
        return "This draft was rejected"
    return None


@dataclass(frozen=True)
class SubmittableResume:
    """One option in "Which resume did you send?". `reason` says why it is disabled."""

    id: int
    kind: ResumeKind
    status: ReviewStatus
    date: datetime  # when the base resume was last saved, or the tailored one was decided or made
    submittable: bool
    reason: str | None


def submittable_options(
    application_id: int, tailored: Sequence[Resume], base: Resume | None
) -> list[SubmittableResume]:
    """The tailored resumes of the application (in the order given), then the base resume when
    one exists. The base resume is always submittable: the user wrote it."""
    options = []
    for resume in tailored:
        reason = unsubmittable_reason(resume, application_id)
        date = resume.reviewed_at or resume.created_at
        options.append(
            SubmittableResume(
                resume.id, ResumeKind.TAILORED, resume.status, date, reason is None, reason
            )
        )
    if base is not None:
        options.append(
            SubmittableResume(base.id, ResumeKind.BASE, base.status, base.updated_at, True, None)
        )
    return options


# --- the three steps ----------------------------------------------------------------------------


class StepKey(enum.Enum):
    ANALYSIS = "analysis"
    TAILORED = "tailored"
    APPLY = "apply"


class StepStatus(enum.Enum):
    DONE = "done"
    CURRENT = "current"
    AVAILABLE = "available"
    LOCKED = "locked"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class WorkflowStep:
    key: StepKey
    status: StepStatus
    text: str  # the one line shown under the step name


def _review_text(statuses: Sequence[ReviewStatus], none: str, rejected: str) -> str:
    """The line for a step the user must act on, from its newest item."""
    if not statuses:
        return none
    if statuses[0] is ReviewStatus.DRAFT:
        return "Draft waiting for your review"
    return rejected


def workflow_steps(
    *,
    stage: Stage,
    analysis_statuses: Sequence[ReviewStatus],
    tailored_statuses: Sequence[ReviewStatus],
    has_base_resume: bool,
    has_submitted_resume: bool,
) -> list[WorkflowStep]:
    """The three steps, in order. The statuses are newest first. `tailored_statuses` holds
    tailored resumes only: a snapshot of the base resume is not one. "Left Saved" means the stage
    is no longer Saved. Each step checks its rules in order, so the first that holds wins."""
    left_saved = stage is not Stage.SAVED
    analysis_approved = ReviewStatus.APPROVED in analysis_statuses
    tailored_approved = ReviewStatus.APPROVED in tailored_statuses

    if analysis_approved:
        analysis = WorkflowStep(StepKey.ANALYSIS, StepStatus.DONE, "Approved")
    elif left_saved:
        analysis = WorkflowStep(StepKey.ANALYSIS, StepStatus.SKIPPED, "Skipped")
    else:
        text = _review_text(analysis_statuses, "Analyze the posting", "Rejected, analyze again")
        analysis = WorkflowStep(StepKey.ANALYSIS, StepStatus.CURRENT, text)

    if tailored_approved:
        tailored = WorkflowStep(StepKey.TAILORED, StepStatus.DONE, "Approved")
    elif left_saved:
        tailored = WorkflowStep(StepKey.TAILORED, StepStatus.SKIPPED, "Skipped")
    elif not analysis_approved:
        text = "Locked until the analysis is approved"
        tailored = WorkflowStep(StepKey.TAILORED, StepStatus.LOCKED, text)
    else:
        text = _review_text(tailored_statuses, "Write a tailored draft", "Rejected, tailor again")
        tailored = WorkflowStep(StepKey.TAILORED, StepStatus.CURRENT, text)

    if left_saved and has_submitted_resume:
        apply = WorkflowStep(StepKey.APPLY, StepStatus.DONE, "Resume sent")
    elif left_saved:
        apply = WorkflowStep(StepKey.APPLY, StepStatus.SKIPPED, "Withdrawn before applying")
    elif not has_base_resume:
        apply = WorkflowStep(
            StepKey.APPLY, StepStatus.LOCKED, "Locked until you save a base resume"
        )
    elif tailored_approved:
        text = "Ready once you have submitted it"
        apply = WorkflowStep(StepKey.APPLY, StepStatus.CURRENT, text)
    else:
        apply = WorkflowStep(StepKey.APPLY, StepStatus.AVAILABLE, "Pick the resume you sent")

    return [analysis, tailored, apply]
