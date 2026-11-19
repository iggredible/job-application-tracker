from app.models import Application
from app.repositories.applications import ApplicationRepository
from app.schemas.application import ApplicationCreate, ApplicationUpdate


class ApplicationNotFound(Exception):
    """No application has the requested id."""


class ApplicationService:
    def __init__(self, repository: ApplicationRepository) -> None:
        self._repository = repository

    def create(self, data: ApplicationCreate) -> Application:
        # `stage` is not set: the column default `saved` applies.
        application = Application(**data.model_dump())
        self._repository.add(application)
        self._repository.commit()
        self._repository.refresh(application)
        return application

    def list(self) -> list[Application]:
        return self._repository.list_all()

    def get(self, application_id: int) -> Application:
        application = self._repository.get(application_id)
        if application is None:
            raise ApplicationNotFound(application_id)
        return application

    def update(self, application_id: int, data: ApplicationUpdate) -> Application:
        application = self.get(application_id)
        changes = data.model_dump(exclude_unset=True)
        if not changes:
            return application
        for field, value in changes.items():
            setattr(application, field, value)
        self._repository.commit()
        self._repository.refresh(application)
        return application
