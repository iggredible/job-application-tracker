"""MaintenanceRepository: the emptiness check and the truncate behind `seed --reset`."""

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models import Application, Source
from app.repositories.applications import ApplicationRepository
from app.repositories.maintenance import MaintenanceRepository


def add_application(session: Session) -> Application:
    application = Application(
        company="Acme", role="Engineer", source=Source.OTHER, posting_text="Build things."
    )
    return ApplicationRepository(session).add(application)


def test_a_fresh_database_is_empty(db_session: Session) -> None:
    assert MaintenanceRepository(db_session).is_empty() is True


def test_one_row_in_any_table_makes_the_database_not_empty(db_session: Session) -> None:
    add_application(db_session)

    assert MaintenanceRepository(db_session).is_empty() is False


def test_truncate_all_empties_every_table_and_restarts_the_ids(db_session: Session) -> None:
    add_application(db_session)
    add_application(db_session)
    repository = MaintenanceRepository(db_session)

    repository.truncate_all()

    assert repository.is_empty() is True
    assert add_application(db_session).id == 1


def test_truncate_all_leaves_the_migration_history_alone(db_session: Session) -> None:
    MaintenanceRepository(db_session).truncate_all()

    assert db_session.scalar(text("SELECT count(*) FROM alembic_version")) == 1
