from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.clock import Clock, utc_now
from app.core.db import get_session
from app.models import Stage
from app.repositories.applications import ApplicationRepository
from app.repositories.timeline import TimelineRepository
from app.schemas.application import (
    ApplicationCreate,
    ApplicationFields,
    ApplicationList,
    ApplicationRead,
    ApplicationUpdate,
    NoteCreate,
    StageChange,
    TimelineEventRead,
)
from app.services.applications import (
    ApplicationNotFound,
    ApplicationService,
    ApplicationView,
    GuardFailed,
    InvalidTransition,
)

router = APIRouter(prefix="/applications", tags=["applications"])


def get_clock() -> Clock:
    return utc_now


def get_service(
    session: Session = Depends(get_session), clock: Clock = Depends(get_clock)
) -> ApplicationService:
    return ApplicationService(ApplicationRepository(session), TimelineRepository(session), clock)


def _read(view: ApplicationView) -> ApplicationRead:
    return ApplicationRead(
        **ApplicationFields.model_validate(view.application).model_dump(),
        allowed_next_stages=view.allowed_next_stages,
        last_activity_at=view.last_activity_at,
        is_stale=view.is_stale,
        idle_days=view.idle_days,
    )


def _not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="application not found")


@router.post("", response_model=ApplicationRead, status_code=201)
def create_application(
    data: ApplicationCreate, service: ApplicationService = Depends(get_service)
) -> ApplicationRead:
    return _read(service.create(data))


@router.get("", response_model=ApplicationList)
def list_applications(
    stage: Stage | None = None, service: ApplicationService = Depends(get_service)
) -> ApplicationList:
    listing = service.list(stage)
    return ApplicationList(
        items=[_read(view) for view in listing.items],
        counts_by_stage=listing.counts_by_stage,
        stale_count=listing.stale_count,
    )


@router.get("/{application_id}", response_model=ApplicationRead)
def get_application(
    application_id: int, service: ApplicationService = Depends(get_service)
) -> ApplicationRead:
    try:
        return _read(service.get(application_id))
    except ApplicationNotFound:
        raise _not_found() from None


@router.patch("/{application_id}", response_model=ApplicationRead)
def update_application(
    application_id: int,
    data: ApplicationUpdate,
    service: ApplicationService = Depends(get_service),
) -> ApplicationRead:
    try:
        return _read(service.update(application_id, data))
    except ApplicationNotFound:
        raise _not_found() from None


@router.post(
    "/{application_id}/stage",
    response_model=ApplicationRead,
    responses={409: {"description": "Not an allowed transition. Lists the allowed next stages."}},
)
def change_stage(
    application_id: int,
    data: StageChange,
    service: ApplicationService = Depends(get_service),
) -> ApplicationRead:
    try:
        return _read(service.change_stage(application_id, data.to_stage))
    except ApplicationNotFound:
        raise _not_found() from None
    except InvalidTransition as error:
        raise HTTPException(
            status_code=409,
            detail={
                "message": str(error),
                "allowed_next_stages": [stage.value for stage in error.allowed],
            },
        ) from None
    except GuardFailed as error:
        raise HTTPException(status_code=409, detail={"message": error.reason}) from None


@router.post("/{application_id}/notes", response_model=TimelineEventRead, status_code=201)
def add_note(
    application_id: int,
    data: NoteCreate,
    service: ApplicationService = Depends(get_service),
) -> TimelineEventRead:
    try:
        return TimelineEventRead.model_validate(service.add_note(application_id, data.note))
    except ApplicationNotFound:
        raise _not_found() from None


@router.get("/{application_id}/timeline", response_model=list[TimelineEventRead])
def get_timeline(
    application_id: int, service: ApplicationService = Depends(get_service)
) -> list[TimelineEventRead]:
    try:
        return [TimelineEventRead.model_validate(e) for e in service.timeline(application_id)]
    except ApplicationNotFound:
        raise _not_found() from None
