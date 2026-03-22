from pydantic import BaseModel


class Genre(BaseModel):
    id: str
    name: str


class GenreListItem(BaseModel):
    uuid: str
    name: str
