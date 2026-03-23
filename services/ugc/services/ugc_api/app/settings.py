from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", case_sensitive=False)

    app_env: str = Field(alias="APP_ENV")

    # Allows running behind reverse proxy under a prefix (e.g. /ugc)
    root_path: str = Field(alias="ROOT_PATH")

    mongo_uri: str = Field(alias="MONGO_URI")
    mongo_db: str = Field(alias="MONGO_DB")

    # коллекции
    col_likes: str = "likes"
    col_bookmarks: str = "bookmarks"
    col_reviews: str = "reviews"

    @field_validator("root_path")
    @classmethod
    def _normalize_root_path(cls, value: str) -> str:
        v = (value or "").strip()
        if v in {"", "/"}:
            return ""
        if not v.startswith("/"):
            v = f"/{v}"
        return v.rstrip("/")


settings = Settings()
