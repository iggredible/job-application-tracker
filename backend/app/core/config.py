from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


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
