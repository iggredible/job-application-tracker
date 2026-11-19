"""The interfaces services depend on, and the errors they handle."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel

from app.ai.prompts import RenderedPrompt
from app.models import AIFeature


@dataclass(frozen=True)
class AICallRecord:
    """Everything logged for one call. The sink turns it into a row (or keeps it in memory)."""

    application_id: int | None
    feature: AIFeature
    prompt_version: str
    model: str
    request_json: dict[str, Any]
    response_json: dict[str, Any] | None  # None when the call failed
    retrieved_example_ids: list[int]
    input_tokens: int | None
    output_tokens: int | None
    estimated_cost: Decimal | None
    latency_ms: int
    schema_valid: bool
    stop_reason: str | None
    error: str | None


@dataclass(frozen=True)
class AIResult[T: BaseModel]:
    """A validated output and the id of its log row, so artifacts can store the foreign key."""

    output: T
    ai_call_id: int


@runtime_checkable
class LogSink(Protocol):
    def write(self, record: AICallRecord) -> int:
        """Store the record and return its id."""
        ...


@runtime_checkable
class AIClient(Protocol):
    def generate[T: BaseModel](
        self,
        *,
        feature: AIFeature,
        prompt: RenderedPrompt,
        output_model: type[T],
        application_id: int | None = None,
        retrieved_example_ids: list[int] | None = None,
        max_tokens: int | None = None,
    ) -> AIResult[T]:
        """Make one call. Logs one row whether it works or not. On failure, raises an AIError."""
        ...


class AIError(Exception):
    """A call failed. It was logged first, and `ai_call_id` is the id of that row."""

    def __init__(self, message: str, ai_call_id: int) -> None:
        super().__init__(message)
        self.ai_call_id = ai_call_id


class AIAPIError(AIError):
    """The API returned an error or could not be reached."""


class AIRefusalError(AIError):
    """The model refused the request."""


class AITruncatedError(AIError):
    """The output was cut off (token limit or context window), so it cannot be trusted."""


class AIValidationError(AIError):
    """The output did not match the Pydantic model."""


class AIConfigurationError(Exception):
    """The key or model is not configured. No call was made, so nothing was logged."""
