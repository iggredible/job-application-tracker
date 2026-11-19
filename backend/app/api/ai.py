from app.ai.client import AnthropicAIClient
from app.ai.sinks import DatabaseLogSink
from app.ai.types import AIClient
from app.core.config import get_settings
from app.core.db import get_session_factory


def get_ai_client() -> AIClient:
    """FastAPI dependency that provides the AI client. Tests override it with FakeAIClient.

    The model and key come from the environment. The log sink writes `ai_calls` in its own
    transaction, so a rollback in the request does not remove the row.
    """
    return AnthropicAIClient.from_settings(get_settings(), DatabaseLogSink(get_session_factory()))
