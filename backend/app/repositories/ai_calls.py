from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AICall, AIFeature


@dataclass(frozen=True)
class AICallRow:
    """What the metrics read from a call: everything but the request and the response."""

    id: int
    feature: AIFeature
    prompt_version: str
    model: str
    error: str | None
    input_tokens: int | None
    output_tokens: int | None
    estimated_cost: Decimal | None
    latency_ms: int


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

    def list_for_metrics(self) -> list[AICallRow]:
        """Every call, failed ones included, without the large request and response columns."""
        query = select(
            AICall.id,
            AICall.feature,
            AICall.prompt_version,
            AICall.model,
            AICall.error,
            AICall.input_tokens,
            AICall.output_tokens,
            AICall.estimated_cost,
            AICall.latency_ms,
        ).order_by(AICall.id)
        return [AICallRow(*row) for row in self._session.execute(query)]
