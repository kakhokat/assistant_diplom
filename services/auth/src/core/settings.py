from pydantic import Field
from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = Field(alias="PROJECT_NAME")
    APP_ENV: str = Field(alias="APP_ENV")

    DB_RESET_ON_STARTUP: bool = Field(alias="DB_RESET_ON_STARTUP")

    # Postgres
    DB_HOST: str = Field(alias="DB_HOST")
    DB_PORT: int = Field(alias="DB_PORT")
    DB_USER: str = Field(alias="DB_USER")
    DB_PASSWORD: str = Field(alias="DB_PASSWORD")
    DB_NAME: str = Field(alias="DB_NAME")

    # Redis
    REDIS_URL: str = Field(alias="REDIS_URL")

    # JWT
    JWT_SECRET: str = Field(alias="JWT_SECRET")
    JWT_ALGORITHM: str = Field(alias="JWT_ALGORITHM")
    ACCESS_TOKEN_EXPIRES_IN: int = Field(alias="ACCESS_TOKEN_EXPIRES_IN")
    REFRESH_TOKEN_EXPIRES_IN: int = Field(alias="REFRESH_TOKEN_EXPIRES_IN")

    # Docs / OpenAPI
    DOCS_URL: str = Field(alias="DOCS_URL")
    OPENAPI_URL: str = Field(alias="OPENAPI_URL")

    # CORS / Proxy
    CORS_ALLOW_ORIGINS: str = Field(alias="CORS_ALLOW_ORIGINS")
    PROXY_TRUSTED_HOSTS: str = Field(alias="PROXY_TRUSTED_HOSTS")

    # Request id
    REQUEST_ID_HEADER: str = Field(alias="REQUEST_ID_HEADER")

    # Tracing (OTLP -> Jaeger)
    OTEL_ENABLED: bool = Field(alias="OTEL_ENABLED")
    OTEL_SERVICE_NAME: str = Field(alias="OTEL_SERVICE_NAME")
    OTEL_EXPORTER_OTLP_ENDPOINT: str = Field(alias="OTEL_EXPORTER_OTLP_ENDPOINT")
    OTEL_EXPORTER_OTLP_PROTOCOL: str = Field(alias="OTEL_EXPORTER_OTLP_PROTOCOL")

    # Rate limiting
    RATE_LIMIT_ENABLED: bool = Field(alias="RATE_LIMIT_ENABLED")
    RATE_LIMIT_REQUESTS: int = Field(alias="RATE_LIMIT_REQUESTS")
    RATE_LIMIT_WINDOW_SECONDS: int = Field(alias="RATE_LIMIT_WINDOW_SECONDS")
    RATE_LIMIT_FAIL_OPEN: bool = Field(alias="RATE_LIMIT_FAIL_OPEN")

    # Internal integration
    INTERNAL_API_KEY: str = Field(alias="INTERNAL_API_KEY")

    # Bootstrap admin (local/prod-like demo)
    BOOTSTRAP_ADMIN_ENABLED: bool = Field(alias="BOOTSTRAP_ADMIN_ENABLED")
    BOOTSTRAP_ADMIN_LOGIN: str = Field(alias="BOOTSTRAP_ADMIN_LOGIN")
    BOOTSTRAP_ADMIN_PASSWORD: str = Field(alias="BOOTSTRAP_ADMIN_PASSWORD")

    # OAuth (Yandex)
    YANDEX_OAUTH_CLIENT_ID: str = Field(alias="YANDEX_OAUTH_CLIENT_ID")
    YANDEX_OAUTH_CLIENT_SECRET: str = Field(alias="YANDEX_OAUTH_CLIENT_SECRET")
    YANDEX_OAUTH_REDIRECT_URI: str = Field(alias="YANDEX_OAUTH_REDIRECT_URI")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()
