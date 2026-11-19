from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.ai.types import AIClient, AIError
from app.api.ai import get_ai_client
from app.api.applications import get_clock
from app.core.clock import Clock
from app.core.db import get_session
from app.repositories.applications import ApplicationRepository
from app.repositories.locks import GenerationLockRepository
from app.repositories.posting_analyses import PostingAnalysisRepository
from app.schemas.analysis import AnalysisRead
from app.services.analysis import (
    AnalysisInProgress,
    AnalysisNotFound,
    AnalysisView,
    PostingAnalysisService,
)
from app.services.applications import ApplicationNotFound
from app.services.review import NotReviewable

router = APIRouter(tags=["analysis"])


def get_service(
    session: Session = Depends(get_session), clock: Clock = Depends(get_clock)
) -> PostingAnalysisService:
    return PostingAnalysisService(
        PostingAnalysisRepository(session),
        ApplicationRepository(session),
        GenerationLockRepository(session),
        clock,
    )


def _read(view: AnalysisView) -> AnalysisRead:
    analysis = view.analysis
    return AnalysisRead(
        id=analysis.id,
        application_id=analysis.application_id,
        status=analysis.status,
        prompt_version=view.prompt_version,
        requirements=analysis.requirements,  # type: ignore[arg-type]  # validated from dicts
        keywords=analysis.keywords,
        created_at=analysis.created_at,
        reviewed_at=analysis.reviewed_at,
    )


def _application_not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="application not found")


def _analysis_not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="analysis not found")


@router.post(
    "/applications/{application_id}/analysis",
    response_model=AnalysisRead,
    status_code=201,
    responses={
        404: {"description": "No such application."},
        409: {"description": "An analysis for this application is already running."},
        502: {"description": "The AI call failed. It is logged, and nothing was saved."},
        503: {"description": "The AI key or model is not configured."},
    },
)
def run_analysis(
    application_id: int,
    service: PostingAnalysisService = Depends(get_service),
    ai: AIClient = Depends(get_ai_client),
) -> AnalysisRead:
    """Make one AI call for the application's posting and save the result as a draft."""
    try:
        return _read(service.run(application_id, ai))
    except ApplicationNotFound:
        raise _application_not_found() from None
    except AnalysisInProgress:
        raise HTTPException(
            status_code=409, detail="An analysis is already running for this application."
        ) from None
    except AIError:
        # The detail is in ai_calls.error. The user only needs to know to try again.
        raise HTTPException(status_code=502, detail="The analysis failed. Try again.") from None


@router.get(
    "/applications/{application_id}/analysis",
    response_model=AnalysisRead | None,
    responses={404: {"description": "No such application."}},
)
def get_analysis(
    application_id: int, service: PostingAnalysisService = Depends(get_service)
) -> AnalysisRead | None:
    """The analysis to display, or null when the application has none."""
    try:
        view = service.get_for_display(application_id)
    except ApplicationNotFound:
        raise _application_not_found() from None
    return _read(view) if view else None


@router.post(
    "/analyses/{analysis_id}/approve",
    response_model=AnalysisRead,
    responses={
        404: {"description": "No such analysis."},
        409: {"description": "The analysis has already been approved or rejected."},
    },
)
def approve_analysis(
    analysis_id: int, service: PostingAnalysisService = Depends(get_service)
) -> AnalysisRead:
    try:
        return _read(service.approve(analysis_id))
    except AnalysisNotFound:
        raise _analysis_not_found() from None
    except NotReviewable as error:
        raise HTTPException(status_code=409, detail=str(error)) from None


@router.post(
    "/analyses/{analysis_id}/reject",
    response_model=AnalysisRead,
    responses={
        404: {"description": "No such analysis."},
        409: {"description": "The analysis has already been approved or rejected."},
    },
)
def reject_analysis(
    analysis_id: int, service: PostingAnalysisService = Depends(get_service)
) -> AnalysisRead:
    try:
        return _read(service.reject(analysis_id))
    except AnalysisNotFound:
        raise _analysis_not_found() from None
    except NotReviewable as error:
        raise HTTPException(status_code=409, detail=str(error)) from None
