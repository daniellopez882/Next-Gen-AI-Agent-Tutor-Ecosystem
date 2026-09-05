"""
Configuration.

The previous code read the environment in three modules and validated nothing.
``llm_config.py`` fell back to ``ChatOpenAI(openai_api_key="mock_key")`` when no
key was set -- an object that constructs and then fails deep inside crewai. The
API that calls those models was open to any caller.
"""

from __future__ import annotations

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

INSECURE_API_KEY = "changeme-in-production"
DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-5"
DEFAULT_OPENAI_MODEL = "gpt-4o"

_LOG_LEVELS = frozenset({"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"})


def _split(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"

    # The tutor endpoint calls paid models on every request.
    API_KEY: str = INSECURE_API_KEY
    CORS_ALLOW_ORIGINS: str = ""

    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = DEFAULT_OPENAI_MODEL
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = DEFAULT_ANTHROPIC_MODEL

    # Storage.
    DB_PATH: str = "tutor.db"
    CHROMA_PATH: str = "chroma_db"

    # Request handling.
    MAX_TASK_CHARS: int = Field(default=2_000, ge=1)
    LLM_TIMEOUT_SECONDS: float = Field(default=60.0, gt=0)

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.strip().lower() == "production"

    @property
    def cors_origins(self) -> list[str]:
        return _split(self.CORS_ALLOW_ORIGINS)

    @property
    def has_insecure_api_key(self) -> bool:
        return self.API_KEY == INSECURE_API_KEY or not self.API_KEY.strip()

    @property
    def has_model_provider(self) -> bool:
        return bool(self.OPENAI_API_KEY.strip() or self.ANTHROPIC_API_KEY.strip())

    @model_validator(mode="after")
    def _normalise(self) -> Settings:
        level = self.LOG_LEVEL.strip().upper()
        if level not in _LOG_LEVELS:
            raise ValueError(
                f"LOG_LEVEL={self.LOG_LEVEL!r} is not one of {sorted(_LOG_LEVELS)}"
            )
        object.__setattr__(self, "LOG_LEVEL", level)
        return self

    def problems(self) -> list[str]:
        found: list[str] = []
        if self.has_insecure_api_key:
            found.append(
                "API_KEY is the placeholder; the tutor endpoint would be open to any caller."
            )
        if not self.has_model_provider:
            found.append(
                "No model provider key is set (OPENAI_API_KEY or ANTHROPIC_API_KEY)."
            )
        if not self.cors_origins:
            found.append(
                "CORS_ALLOW_ORIGINS is empty; browsers on other origins would be refused."
            )
        return found

    def validate_production(self) -> None:
        problems = self.problems()
        if problems:
            raise ValueError(
                "Invalid production configuration:\n  - " + "\n  - ".join(problems)
            )


settings = Settings()
