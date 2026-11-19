from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.applications import get_clock
from app.api.coverage import read_coverage
from app.api.tailored_resumes import read_draft
from app.core.clock import Clock
from app.core.db import get_session
from app.repositories.applications import ApplicationRepository
from app.repositories.posting_analyses import PostingAnalysisRepository
from app.repositories.resumes import ResumeRepository
from app.schemas.resume import ResumeWrite
from app.schemas.tailored_resume import TailoredResumeEditRead, TailoredResumeRead
from app.services.coverage import CoverageService
from app.services.resume_review import NotEditable, TailoredResumeNotFound, TailoredReviewService
from app.services.review import NotReviewable

router = APIRouter(tags=["tailored resumes"])


def get_service(
    session: Session = Depends(get_session), clock: Clock = Depends(get_clock)
) -> TailoredReviewService:
    resumes = ResumeRepository(session)
    analyses = PostingAnalysisRepository(session)
    return TailoredReviewService(
        resumes,
        analyses,
        CoverageService(analyses, ApplicationRepository(session), resumes),
        clock,
    )


def _not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="resume not found")


@router.patch(
    "/resumes/{resume_id}",
    response_model=TailoredResumeEditRead,
    responses={
        404: {"description": "No such tailored resume (the base resume is not one)."},
        409: {"description": "The resume has already been approved or rejected."},
        422: {"description": "The text is blank, or the body has a field other than the text."},
    },
)
def save_edits(
    resume_id: int, data: ResumeWrite, service: TailoredReviewService = Depends(get_service)
) -> TailoredResumeEditRead:
    """Save the edited text of a draft. Only `content_markdown` changes. The response has the
    current guardrail flags and the coverage of the new text, calculated now."""
    try:
        saved = service.save_edits(resume_id, data.content_markdown)
    except TailoredResumeNotFound:
        raise _not_found() from None
    except NotEditable as error:
        raise HTTPException(status_code=409, detail=str(error)) from None
    return TailoredResumeEditRead(
        **read_draft(saved.draft).model_dump(), coverage=read_coverage(saved.coverage)
    )


@router.post(
    "/resumes/{resume_id}/approve",
    response_model=TailoredResumeRead,
    responses={
        404: {"description": "No such tailored resume (the base resume is not one)."},
        409: {"description": "The resume has already been approved or rejected."},
    },
)
def approve_resume(
    resume_id: int, service: TailoredReviewService = Depends(get_service)
) -> TailoredResumeRead:
    """Approve a draft. It becomes read-only, and the review time is recorded. Unsaved edits are
    not part of this call: save them first with PATCH."""
    try:
        return read_draft(service.approve(resume_id))
    except TailoredResumeNotFound:
        raise _not_found() from None
    except NotReviewable as error:
        raise HTTPException(status_code=409, detail=str(error)) from None


@router.post(
    "/resumes/{resume_id}/reject",
    response_model=TailoredResumeRead,
    responses={
        404: {"description": "No such tailored resume (the base resume is not one)."},
        409: {"description": "The resume has already been approved or rejected."},
    },
)
def reject_resume(
    resume_id: int, service: TailoredReviewService = Depends(get_service)
) -> TailoredResumeRead:
    """Reject a draft. It becomes read-only, and the review time is recorded. To try again, tailor
    the resume again."""
    try:
        return read_draft(service.reject(resume_id))
    except TailoredResumeNotFound:
        raise _not_found() from None
    except NotReviewable as error:
        raise HTTPException(status_code=409, detail=str(error)) from None
