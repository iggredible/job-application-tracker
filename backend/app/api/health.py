from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.repositories.health import HealthRepository
from app.schemas.health import HealthResponse
from app.services.health import DatabaseUnavailable, HealthService

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health(session: Session = Depends(get_session)) -> HealthResponse:
    try:
        HealthService(HealthRepository(session)).check()
    except DatabaseUnavailable:
        raise HTTPException(status_code=503, detail="database unavailable") from None
    return HealthResponse(status="ok")
