"""Application settings, loaded from environment / .env."""
from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    postgres_user: str = "analytics"
    postgres_password: str = "analytics"
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "analytics"

    # Read-only role used to execute /query and /nl-query SQL.
    ro_user: str = "analytics_ro"
    ro_password: str = "readonly"

    # JWT / auth
    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    # Ad-hoc query guardrail: hard cap on returned rows.
    query_max_rows: int = 1000

    # NL-to-SQL assistant (Google Gemini). Set GEMINI_API_KEY in the env / .env.
    # Provider "echo" runs offline (no LLM call), used for tests/demos.
    llm_provider: str = "gemini"           # "gemini" | "echo"
    llm_model: str = "gemini-3.6-flash"
    gemini_api_key: str | None = None      # from GEMINI_API_KEY

    # Fallback provider: used automatically if Gemini errors (e.g. quota
    # exhausted) and a GROQ_API_KEY is configured. Groq exposes an
    # OpenAI-compatible API, so it's called via the `openai` SDK pointed at
    # Groq's base URL.
    groq_api_key: str | None = None        # from GROQ_API_KEY
    groq_model: str = "openai/gpt-oss-120b"
    # Smaller/cheaper model tried when `groq_model` hits a 429 (rate limit) —
    # Groq enforces per-model tokens-per-minute budgets, so a lighter model
    # often still has headroom even while the primary one is throttled.
    groq_fallback_model: str = "llama-3.1-8b-instant"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def readonly_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.ro_user}:{self.ro_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


settings = Settings()
