from pydantic import BaseModel


class PersonFilmRef(BaseModel):
    uuid: str
    title: str
    roles: list[str] = []


class Person(BaseModel):
    id: str
    full_name: str
    aliases: list[str] = []
    films: list[PersonFilmRef] = []


class PersonListItem(BaseModel):
    uuid: str
    full_name: str
    aliases: list[str] = []
