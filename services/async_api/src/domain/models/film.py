from typing import List, Optional

from pydantic import BaseModel
from pydantic import Field


class Film(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    original_title: Optional[str] = None
    title_aliases: Optional[List[str]] = None
    imdb_rating: Optional[float] = Field(default=None)
    genre: Optional[List[str]] = None
    runtime_minutes: Optional[int] = None
    directors: Optional[List[str]] = None
    actors: Optional[List[str]] = None
    writers: Optional[List[str]] = None


class FilmListItem(BaseModel):
    uuid: str
    title: str
    original_title: Optional[str] = None
    title_aliases: Optional[List[str]] = None
    imdb_rating: Optional[float] = None
    description: Optional[str] = None
    genre: Optional[List[str]] = None
    directors: Optional[List[str]] = None


class FilmDetail(BaseModel):
    uuid: str
    title: str
    original_title: Optional[str] = None
    title_aliases: Optional[List[str]] = None
    imdb_rating: Optional[float] = None
    description: Optional[str] = None
    genre: Optional[list] = None
    runtime_minutes: Optional[int] = None
    directors: Optional[List[str]] = None
    actors: Optional[List[str]] = None
    writers: Optional[List[str]] = None
