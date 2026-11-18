from sqlalchemy.exc import SQLAlchemyError

from app.repositories.health import HealthRepository


class DatabaseUnavailable(Exception):
    """The database did not answer the connection check."""


class HealthService:
    def __init__(self, repository: HealthRepository) -> None:
        self._repository = repository

    def check(self) -> None:
        try:
            self._repository.ping()
        except SQLAlchemyError as exc:
            raise DatabaseUnavailable from exc
