from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.repositories.applications import ApplicationRepository
from app.repositories.posting_analyses import PostingAnalysisRepository
from app.repositories.resumes import ResumeRepository
from app.schemas.coverage import ApplicationCoverageRead, CoverageRead
from app.services.applications import ApplicationNotFound
from app.services.coverage import (
    ApplicationCoverage,
    Coverage,
    CoverageService,
    NoAnalysis,
    ResumeNotFound,
)

router = APIRouter(tags=["coverage"])


def get_service(session: Session = Depends(get_session)) -> CoverageService:
    return CoverageService(
        PostingAnalysisRepository(session),
        ApplicationRepository(session),
        ResumeRepository(session),
    )


def _coverage(coverage: Coverage) -> CoverageRead:
    return CoverageRead(covered=coverage.covered, missing=coverage.missing, ratio=coverage.ratio)


def read_coverage(result: ApplicationCoverage) -> ApplicationCoverageRead:
    return ApplicationCoverageRead(
        **_coverage(result.coverage).model_dump(),
        base=_coverage(result.base) if result.base else None,
        newly_covered=result.newly_covered,
        still_missing=result.still_missing,
    )


@router.get(
    "/applications/{application_id}/coverage",
    response_model=ApplicationCoverageRead,
    response_model_exclude_none=True,
    responses={
        404: {
            "description": (
                "No such application, no analysis to use (none, or only rejected ones), no base "
                "resume, or a resume_id that is neither the base resume nor this application's."
            )
        }
    },
)
def get_coverage(
    application_id: int,
    resume_id: int | None = None,
    service: CoverageService = Depends(get_service),
) -> ApplicationCoverageRead:
    """Which of the posting's keywords a resume contains, calculated now and never stored.

    Uses the latest approved analysis, or the latest draft when none is approved. Without
    `resume_id` it measures the base resume. With it, the response also has `base`,
    `newly_covered` and `still_missing`.
    """
    try:
        return read_coverage(service.for_application(application_id, resume_id))
    except ApplicationNotFound:
        raise HTTPException(status_code=404, detail="application not found") from None
    except NoAnalysis:
        raise HTTPException(status_code=404, detail="analysis not found") from None
    except ResumeNotFound:
        raise HTTPException(status_code=404, detail="resume not found") from None
