from collections.abc import Callable

from sqlalchemy.orm import Session

from app.ai.types import AICallRecord
from app.models import AICall
from app.repositories.ai_calls import AICallRepository


class DatabaseLogSink:
    """The app's sink: writes `ai_calls`.

    It opens its own session and commits, so the row survives a rollback in the caller's
    transaction. Because it uses its own connection, `application_id` must belong to an
    application that is already committed.
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def write(self, record: AICallRecord) -> int:
        with self._session_factory() as session:
            call = AICallRepository(session).add(
                AICall(
                    application_id=record.application_id,
                    feature=record.feature,
                    prompt_version=record.prompt_version,
                    model=record.model,
                    request_json=record.request_json,
                    response_json=record.response_json,
                    retrieved_example_ids=record.retrieved_example_ids,
                    input_tokens=record.input_tokens,
                    output_tokens=record.output_tokens,
                    estimated_cost=record.estimated_cost,
                    latency_ms=record.latency_ms,
                    schema_valid=record.schema_valid,
                    stop_reason=record.stop_reason,
                    error=record.error,
                )
            )
            session.commit()
            return call.id


class InMemoryLogSink:
    """Keeps records in a list. The eval (feature 16) uses it so it never writes to the app
    database. Ids start at 1, like the table's."""

    def __init__(self) -> None:
        self.records: list[AICallRecord] = []

    def write(self, record: AICallRecord) -> int:
        self.records.append(record)
        return len(self.records)
