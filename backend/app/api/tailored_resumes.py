from dataclasses import asdict

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
from app.repositories.resumes import ResumeRepository
from app.schemas.tailored_resume import GuardrailFlag, TailoredResumeRead
from app.services.applications import ApplicationNotFound
from app.services.resume_review import TailoredDraft
from app.services.tailoring import (
    TailoredResumeService,
    TailoringBlocked,
    TailoringInProgress,
)

router = APIRouter(tags=["tailored resumes"])


def get_service(
    session: Session = Depends(get_session), clock: Clock = Depends(get_clock)
) -> TailoredResumeService:
    return TailoredResumeService(
        ResumeRepository(session),
        PostingAnalysisRepository(session),
        ApplicationRepository(session),
        GenerationLockRepository(session),
        clock,
    )


def read_draft(draft: TailoredDraft) -> TailoredResumeRead:
    resume = draft.resume
    return TailoredResumeRead(
        id=resume.id,
        application_id=resume.application_id,  # type: ignore[arg-type]  # set on tailored ones
        status=resume.status,
        prompt_version=resume.ai_call.prompt_version,  # type: ignore[union-attr]
        content_markdown=resume.content_markdown,
        guardrail_flags=[GuardrailFlag(**asdict(flag)) for flag in draft.flags],
        created_at=resume.created_at,
        reviewed_at=resume.reviewed_at,
        outcome=draft.outcome,
        displayed=draft.displayed,
    )


def _application_not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="application not found")


@router.post(
    "/applications/{application_id}/tailored-resumes",
    response_model=TailoredResumeRead,
    status_code=201,
    responses={
        404: {"description": "No such application."},
        409: {
            "description": (
                "There is no approved posting analysis or no base resume (the detail says "
                "which), or a tailoring for this application is already running."
            )
        },
        502: {"description": "The AI call failed. It is logged, and nothing was saved."},
        503: {"description": "The AI key or model is not configured."},
    },
)
def run_tailoring(
    application_id: int,
    service: TailoredResumeService = Depends(get_service),
    ai: AIClient = Depends(get_ai_client),
) -> TailoredResumeRead:
    """Make one AI call and save the tailored resume as a draft."""
    try:
        return read_draft(service.run(application_id, ai))
    except ApplicationNotFound:
        raise _application_not_found() from None
    except TailoringBlocked as blocked:
        raise HTTPException(status_code=409, detail=blocked.reason) from None
    except TailoringInProgress:
        raise HTTPException(
            status_code=409, detail="A tailoring is already running for this application."
        ) from None
    except AIError:
        # The detail is in ai_calls.error. The user only needs to know to try again.
        raise HTTPException(status_code=502, detail="The tailoring failed. Try again.") from None


@router.get(
    "/applications/{application_id}/tailored-resumes",
    response_model=list[TailoredResumeRead],
    responses={404: {"description": "No such application."}},
)
def list_tailored_resumes(
    application_id: int, service: TailoredResumeService = Depends(get_service)
) -> list[TailoredResumeRead]:
    """The application's tailored resumes, newest first. One has `displayed` set: the one the
    Tailored resume section shows."""
    try:
        return [read_draft(draft) for draft in service.list_for_application(application_id)]
    except ApplicationNotFound:
        raise _application_not_found() from None
