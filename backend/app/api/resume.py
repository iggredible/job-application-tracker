from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.applications import get_clock
from app.core.clock import Clock
from app.core.db import get_session
from app.repositories.resumes import ResumeRepository
from app.schemas.resume import ResumeRead, ResumeWrite
from app.services.resumes import ResumeNotFound, ResumeService

router = APIRouter(prefix="/resume", tags=["resume"])


def get_service(
    session: Session = Depends(get_session), clock: Clock = Depends(get_clock)
) -> ResumeService:
    return ResumeService(ResumeRepository(session), clock)


@router.get(
    "",
    response_model=ResumeRead,
    responses={404: {"description": "No base resume has been saved yet."}},
)
def get_resume(service: ResumeService = Depends(get_service)) -> ResumeRead:
    try:
        return ResumeRead.model_validate(service.get_base())
    except ResumeNotFound:
        raise HTTPException(status_code=404, detail="resume not found") from None


@router.put("", response_model=ResumeRead)
def put_resume(data: ResumeWrite, service: ResumeService = Depends(get_service)) -> ResumeRead:
    """Create the base resume, or replace it. Either way the result is the one base resume."""
    return ResumeRead.model_validate(service.save_base(data.content_markdown))
