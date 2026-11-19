from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


@dataclass(frozen=True)
class ModelPrice:
    """Dollars per million tokens."""

    input_per_mtok: Decimal
    output_per_mtok: Decimal


# Estimated-cost prices, keyed by model ID. Source: https://platform.claude.com/docs/en/about-claude/pricing
# (checked 2026-11-19). A model that is not listed gets a null cost, never a guess.
# The table is flat on purpose. Haiku 5.5 bills $0.50 / $2.50 for prompts over 100,000 tokens;
# a posting plus a resume is far below that. Caching, batch and fast-mode pricing are ignored.
MODEL_PRICES: dict[str, ModelPrice] = {
    "claude-sonnet-5-5": ModelPrice(Decimal("2"), Decimal("10")),
    "claude-opus-5-5": ModelPrice(Decimal("4"), Decimal("20")),
    "claude-haiku-5-5": ModelPrice(Decimal("0.10"), Decimal("0.50")),
    "claude-fable-5-2": ModelPrice(Decimal("8"), Decimal("40")),
}


class Settings(BaseSettings):
    """Configuration read from environment variables (and ../.env in local development)."""

    model_config = SettingsConfigDict(env_file="../.env", extra="ignore")

    database_url: str = "postgresql+psycopg://localhost/job_tracker"
    test_database_url: str = "postgresql+psycopg://localhost/job_tracker_test"
    anthropic_api_key: SecretStr = SecretStr("")
    anthropic_model: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
