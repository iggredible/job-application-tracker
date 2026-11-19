from sqlalchemy.orm import Session

from app.models import AICall


class AICallRepository:
    """`ai_calls` is append-only: this repository can add and read, never change or delete."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, call: AICall) -> AICall:
        """Insert the row and flush so its id is available. The caller commits."""
        self._session.add(call)
        self._session.flush()
        return call

    def get(self, ai_call_id: int) -> AICall | None:
        return self._session.get(AICall, ai_call_id)
