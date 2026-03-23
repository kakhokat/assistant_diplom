from fastapi import Query
from pydantic import BaseModel, field_validator

from core.settings import settings

DEFAULT_PAGE_SIZE = settings.PAGE_SIZE_DEFAULT
MAX_PAGE_SIZE = settings.PAGE_SIZE_MAX


class PaginationParams(BaseModel):
    page_number: int
    page_size: int

    @field_validator("page_number")
    @classmethod
    def validate_number(cls, v: int) -> int:
        if v < 1:
            raise ValueError("page_number must be >= 1")
        return v

    @field_validator("page_size")
    @classmethod
    def validate_size(cls, v: int) -> int:
        if v < 1:
            raise ValueError("page_size must be >= 1")
        if v > MAX_PAGE_SIZE:
            raise ValueError(f"page_size must be <= {MAX_PAGE_SIZE}")
        return v

    def __init__(
        self,
        page_number: int = Query(default=1, ge=1, description="Номер страницы (с 1)"),
        page_size: int = Query(
            default=DEFAULT_PAGE_SIZE,
            ge=1,
            le=MAX_PAGE_SIZE,
            description="Размер страницы",
        ),
    ):
        super().__init__(page_number=page_number, page_size=page_size)
