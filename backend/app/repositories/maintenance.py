from sqlalchemy import literal, select, text
from sqlalchemy.orm import Session

from app.models import Base


class MaintenanceRepository:
    """Whole-database queries for the seed script. Every table the models define, nothing else:
    `alembic_version` is not a model, so it is never counted or truncated."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def is_empty(self) -> bool:
        return all(
            self._session.scalar(select(literal(1)).select_from(table).limit(1)) is None
            for table in Base.metadata.sorted_tables
        )

    def truncate_all(self) -> None:
        """Empty every table and restart its ids. TRUNCATE is not blocked by the append-only
        triggers, and the tables reference each other in a cycle, so they go in one statement."""
        names = ", ".join(f'"{table.name}"' for table in Base.metadata.sorted_tables)
        self._session.execute(text(f"TRUNCATE {names} RESTART IDENTITY CASCADE"))
