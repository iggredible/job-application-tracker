"""The one place that calls Anthropic.

Every call goes through `AnthropicAIClient.generate()`. It asks for structured output, checks
the stop reason, validates with Pydantic, and writes exactly one log record, success or failure.

It calls `messages.create` and validates the text itself rather than using the SDK's
`messages.parse`. `parse` validates inside the SDK call, so a response cut off at the token
limit would raise a bare ValidationError before the stop reason could be checked.
"""

import time
from typing import Any

import anthropic
from pydantic import BaseModel, ValidationError

from app.ai.cost import estimate_cost
from app.ai.prompts import RenderedPrompt
from app.ai.types import (
    AIAPIError,
    AICallRecord,
    AIConfigurationError,
    AIError,
    AIRefusalError,
    AIResult,
    AITruncatedError,
    AIValidationError,
    LogSink,
)
from app.core.config import MODEL_PRICES, ModelPrice, Settings
from app.models import AIFeature

# Large enough for a full resume as structured output, so normal calls are not cut off.
DEFAULT_MAX_TOKENS = 8192
# The error column holds a kind and a short detail, not a whole response.
MAX_ERROR_LENGTH = 2000
# Stop reasons that mean the output may be incomplete.
TRUNCATED_STOP_REASONS = {"max_tokens", "model_context_window_exceeded"}


class AnthropicAIClient:
    def __init__(
        self,
        sdk: anthropic.Anthropic,
        *,
        model: str,
        sink: LogSink,
        prices: dict[str, ModelPrice] = MODEL_PRICES,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> None:
        self.sdk = sdk
        self.model = model
        self.sink = sink
        self._prices = prices
        self._max_tokens = max_tokens

    @classmethod
    def from_settings(cls, settings: Settings, sink: LogSink) -> "AnthropicAIClient":
        """The key and model come from the environment (ANTHROPIC_API_KEY, ANTHROPIC_MODEL)."""
        api_key = settings.anthropic_api_key.get_secret_value()
        if not api_key:
            raise AIConfigurationError("ANTHROPIC_API_KEY is not set")
        if not settings.anthropic_model:
            raise AIConfigurationError("ANTHROPIC_MODEL is not set")
        return cls(anthropic.Anthropic(api_key=api_key), model=settings.anthropic_model, sink=sink)

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
        # No temperature: reproducibility comes from the stored request and response.
        request: dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens or self._max_tokens,
            "system": prompt.system,
            "messages": [{"role": "user", "content": prompt.user}],
            "output_config": {
                "format": {
                    "type": "json_schema",
                    "schema": anthropic.transform_schema(output_model),
                }
            },
        }

        def log(
            *,
            latency_ms: int,
            response: BaseModel | None = None,
            message: anthropic.types.Message | None = None,
            error: str | None = None,
        ) -> int:
            usage = message.usage if message is not None else None
            input_tokens = usage.input_tokens if usage else None
            output_tokens = usage.output_tokens if usage else None
            return self.sink.write(
                AICallRecord(
                    application_id=application_id,
                    feature=feature,
                    prompt_version=prompt.version,
                    model=self.model,
                    request_json=request,
                    response_json=response.model_dump(mode="json") if response else None,
                    retrieved_example_ids=retrieved_example_ids or [],
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    estimated_cost=estimate_cost(
                        self.model, input_tokens, output_tokens, self._prices
                    ),
                    latency_ms=latency_ms,
                    schema_valid=error is None,
                    stop_reason=message.stop_reason if message is not None else None,
                    error=error[:MAX_ERROR_LENGTH] if error else None,
                )
            )

        def fail(
            error_class: type[AIError],
            kind: str,
            detail: str,
            *,
            latency_ms: int,
            message: anthropic.types.Message | None = None,
        ) -> AIError:
            ai_call_id = log(latency_ms=latency_ms, message=message, error=f"{kind}: {detail}")
            return error_class(f"{kind}: {detail}"[:MAX_ERROR_LENGTH], ai_call_id)

        started = time.perf_counter()
        try:
            message = self.sdk.messages.create(**request)
        except anthropic.APIError as exc:
            latency_ms = _elapsed_ms(started)
            raise fail(
                AIAPIError, "api_error", f"{type(exc).__name__}: {exc}", latency_ms=latency_ms
            ) from exc
        latency_ms = _elapsed_ms(started)

        # The stop reason comes before parsing: a refusal or a cut-off response cannot be
        # trusted, even when its text happens to look like valid JSON.
        if message.stop_reason == "refusal":
            raise fail(
                AIRefusalError, "refusal", "the model refused the request",
                latency_ms=latency_ms, message=message,
            )  # fmt: skip
        if message.stop_reason in TRUNCATED_STOP_REASONS:
            raise fail(
                AITruncatedError, "truncated", f"stopped with {message.stop_reason}",
                latency_ms=latency_ms, message=message,
            )  # fmt: skip

        text = next((block.text for block in message.content if block.type == "text"), "")
        try:
            output = output_model.model_validate_json(text)
        except ValidationError as exc:
            raise fail(
                AIValidationError, "validation_error", str(exc),
                latency_ms=latency_ms, message=message,
            ) from exc  # fmt: skip

        ai_call_id = log(latency_ms=latency_ms, response=output, message=message)
        return AIResult(output=output, ai_call_id=ai_call_id)


def _elapsed_ms(started: float) -> int:
    return round((time.perf_counter() - started) * 1000)
