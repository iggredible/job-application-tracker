from sqlalchemy import text
from sqlalchemy.orm import Session


class HealthRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def ping(self) -> None:
        """Run the cheapest possible query. Raises if the database cannot be reached."""
        self._session.execute(text("SELECT 1"))
