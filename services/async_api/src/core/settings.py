from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = Field(alias="PROJECT_NAME")
    REDIS_URL: str = Field(alias="REDIS_URL")
    ELASTIC_URL: str = Field(alias="ELASTIC_URL")

    ES_INDEX_FILMS: str = Field(alias="ES_INDEX_FILMS")
    ES_INDEX_GENRES: str = Field(alias="ES_INDEX_GENRES")
    ES_INDEX_PERSONS: str = Field(alias="ES_INDEX_PERSONS")

    DOCS_URL: str = Field(alias="DOCS_URL")
    OPENAPI_URL: str = Field(alias="OPENAPI_URL")

    CORS_ALLOW_ORIGINS: str = Field(alias="CORS_ALLOW_ORIGINS")
    PROXY_TRUSTED_HOSTS: str = Field(alias="PROXY_TRUSTED_HOSTS")

    JWT_SECRET: str = Field(alias="JWT_SECRET")
    JWT_ALGORITHM: str = Field(alias="JWT_ALGORITHM")
    JWT_ISSUER: str = Field(alias="JWT_ISSUER")
    JWT_AUDIENCE: str = Field(alias="JWT_AUDIENCE")

    PAGE_SIZE_DEFAULT: int = Field(alias="PAGE_SIZE_DEFAULT")
    PAGE_SIZE_MAX: int = Field(alias="PAGE_SIZE_MAX")

    FILM_CACHE_TTL: int = Field(alias="FILM_CACHE_TTL")
    GENRE_CACHE_TTL: int = Field(alias="GENRE_CACHE_TTL")
    PERSON_CACHE_TTL: int = Field(alias="PERSON_CACHE_TTL")

    ES_WAIT_TIMEOUT: int = Field(alias="ES_WAIT_TIMEOUT")
    ES_MAPPING_PATH: str = Field(alias="ES_MAPPING_PATH")
    ES_BULK_PATH: str = Field(alias="ES_BULK_PATH")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()
