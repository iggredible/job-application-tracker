from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models import AIFeature


class GenerationLockRepository:
    """One Postgres advisory lock per application and AI feature."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def try_lock(self, feature: AIFeature, application_id: int) -> bool:
        """Take the lock without waiting. Returns False when another transaction holds it.

        It is a transaction-level lock: it is released when this session commits or rolls back
        (or closes), so a crashed request cannot leave it held. Asking again from the same
        session succeeds, because advisory locks are reentrant within one session.
        """
        key = f"{feature.value}:{application_id}"
        acquired = self._session.scalar(
            text("SELECT pg_try_advisory_xact_lock(hashtextextended(:key, 0))"), {"key": key}
        )
        return bool(acquired)
