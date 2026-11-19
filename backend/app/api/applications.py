from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.repositories.applications import ApplicationRepository
from app.schemas.application import ApplicationCreate, ApplicationRead, ApplicationUpdate
from app.services.applications import ApplicationNotFound, ApplicationService

router = APIRouter(prefix="/applications", tags=["applications"])


def get_service(session: Session = Depends(get_session)) -> ApplicationService:
    return ApplicationService(ApplicationRepository(session))


@router.post("", response_model=ApplicationRead, status_code=201)
def create_application(
    data: ApplicationCreate, service: ApplicationService = Depends(get_service)
) -> ApplicationRead:
    return ApplicationRead.model_validate(service.create(data))


@router.get("", response_model=list[ApplicationRead])
def list_applications(service: ApplicationService = Depends(get_service)) -> list[ApplicationRead]:
    return [ApplicationRead.model_validate(a) for a in service.list()]


@router.get("/{application_id}", response_model=ApplicationRead)
def get_application(
    application_id: int, service: ApplicationService = Depends(get_service)
) -> ApplicationRead:
    try:
        return ApplicationRead.model_validate(service.get(application_id))
    except ApplicationNotFound:
        raise HTTPException(status_code=404, detail="application not found") from None


@router.patch("/{application_id}", response_model=ApplicationRead)
def update_application(
    application_id: int,
    data: ApplicationUpdate,
    service: ApplicationService = Depends(get_service),
) -> ApplicationRead:
    try:
        return ApplicationRead.model_validate(service.update(application_id, data))
    except ApplicationNotFound:
        raise HTTPException(status_code=404, detail="application not found") from None
