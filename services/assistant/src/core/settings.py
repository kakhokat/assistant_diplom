from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    PROJECT_NAME: str = Field(alias="PROJECT_NAME")
    DOCS_URL: str = Field(alias="DOCS_URL")
    OPENAPI_URL: str = Field(alias="OPENAPI_URL")

    AUTH_API_BASE_URL: str = Field(alias="AUTH_API_BASE_URL")
    CATALOG_API_BASE_URL: str = Field(alias="CATALOG_API_BASE_URL")
    UGC_API_BASE_URL: str = Field(alias="UGC_API_BASE_URL")

    ASSISTANT_SESSION_REDIS_URL: str = Field(alias="ASSISTANT_SESSION_REDIS_URL")
    ASSISTANT_SESSION_TTL_SECONDS: int = Field(alias="ASSISTANT_SESSION_TTL_SECONDS")
    ASSISTANT_SESSION_KEY_PREFIX: str = Field(alias="ASSISTANT_SESSION_KEY_PREFIX")

    ASSISTANT_PARSE_CACHE_TTL_SECONDS: int = Field(
        default=86400, alias="ASSISTANT_PARSE_CACHE_TTL_SECONDS"
    )
    ASSISTANT_PARSE_CACHE_KEY_PREFIX: str = Field(
        default="assistant_parse_cache", alias="ASSISTANT_PARSE_CACHE_KEY_PREFIX"
    )
    ASSISTANT_PARSE_CACHE_VERSION: str = Field(
        default="v1", alias="ASSISTANT_PARSE_CACHE_VERSION"
    )

    ASSISTANT_PUBLIC_RESPONSE_CACHE_TTL_SECONDS: int = Field(
        default=900, alias="ASSISTANT_PUBLIC_RESPONSE_CACHE_TTL_SECONDS"
    )
    ASSISTANT_PUBLIC_RESPONSE_CACHE_KEY_PREFIX: str = Field(
        default="assistant_public_response_cache",
        alias="ASSISTANT_PUBLIC_RESPONSE_CACHE_KEY_PREFIX",
    )

    ASSISTANT_FEEDBACK_KEY_PREFIX: str = Field(
        default="assistant_feedback", alias="ASSISTANT_FEEDBACK_KEY_PREFIX"
    )
    ASSISTANT_FEEDBACK_MAX_EVENTS: int = Field(
        default=5000, alias="ASSISTANT_FEEDBACK_MAX_EVENTS"
    )

    ASSISTANT_LLM_FAILURE_THRESHOLD: int = Field(
        default=3, alias="ASSISTANT_LLM_FAILURE_THRESHOLD"
    )
    ASSISTANT_LLM_COOLDOWN_SECONDS: int = Field(
        default=60, alias="ASSISTANT_LLM_COOLDOWN_SECONDS"
    )

    ASSISTANT_SERVICE_LOGIN: str = Field(alias="ASSISTANT_SERVICE_LOGIN")
    ASSISTANT_SERVICE_PASSWORD: str = Field(alias="ASSISTANT_SERVICE_PASSWORD")

    HTTP_TIMEOUT_SECONDS: int = Field(alias="HTTP_TIMEOUT_SECONDS")
    RECOMMENDATION_LIMIT: int = Field(alias="RECOMMENDATION_LIMIT")

    ASSISTANT_LLM_ENABLED: bool = Field(alias="ASSISTANT_LLM_ENABLED")
    ASSISTANT_LLM_PROVIDER: str = Field(alias="ASSISTANT_LLM_PROVIDER")
    ASSISTANT_LLM_BASE_URL: str = Field(alias="ASSISTANT_LLM_BASE_URL")
    ASSISTANT_LLM_MODEL: str = Field(alias="ASSISTANT_LLM_MODEL")
    ASSISTANT_LLM_TIMEOUT_SECONDS: int = Field(alias="ASSISTANT_LLM_TIMEOUT_SECONDS")

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()
