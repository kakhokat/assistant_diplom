from __future__ import annotations

import httpx

from core.settings import settings


class CatalogClient:
    DEFAULT_PAGE_NUMBER = 1
    SEARCH_PAGE_SIZE = 10
    FILMS_BY_GENRE_PAGE_SIZE = 20

    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    async def search_films(self, query: str, authorization: str) -> list[dict]:
        resp = await self.client.get(
            f"{settings.CATALOG_API_BASE_URL}/api/v1/films/search",
            params={
                "query": query,
                "page_number": self.DEFAULT_PAGE_NUMBER,
                "page_size": self.SEARCH_PAGE_SIZE,
            },
            headers={"Authorization": authorization},
        )
        resp.raise_for_status()
        return resp.json()

    async def list_top_films(self, authorization: str, limit: int = 10) -> list[dict]:
        resp = await self.client.get(
            f"{settings.CATALOG_API_BASE_URL}/api/v1/films/",
            params={
                "page_number": self.DEFAULT_PAGE_NUMBER,
                "page_size": limit,
                "sort": "-imdb_rating",
            },
            headers={"Authorization": authorization},
        )
        resp.raise_for_status()
        return resp.json()

    async def film_details(self, film_id: str, authorization: str) -> dict:
        resp = await self.client.get(
            f"{settings.CATALOG_API_BASE_URL}/api/v1/films/{film_id}",
            headers={"Authorization": authorization},
        )
        resp.raise_for_status()
        return resp.json()

    async def search_genres(self, query: str, authorization: str) -> list[dict]:
        resp = await self.client.get(
            f"{settings.CATALOG_API_BASE_URL}/api/v1/genres/search",
            params={
                "query": query,
                "page_number": self.DEFAULT_PAGE_NUMBER,
                "page_size": self.SEARCH_PAGE_SIZE,
            },
            headers={"Authorization": authorization},
        )
        resp.raise_for_status()
        return resp.json()

    async def genre_details(self, genre_id: str, authorization: str) -> dict:
        resp = await self.client.get(
            f"{settings.CATALOG_API_BASE_URL}/api/v1/genres/{genre_id}",
            headers={"Authorization": authorization},
        )
        resp.raise_for_status()
        return resp.json()

    async def films_by_genre(self, genre_id: str, authorization: str) -> list[dict]:
        resp = await self.client.get(
            f"{settings.CATALOG_API_BASE_URL}/api/v1/films/",
            params={
                "page_number": self.DEFAULT_PAGE_NUMBER,
                "page_size": self.FILMS_BY_GENRE_PAGE_SIZE,
                "genre": genre_id,
            },
            headers={"Authorization": authorization},
        )
        resp.raise_for_status()
        return resp.json()

    async def search_persons(self, query: str, authorization: str) -> list[dict]:
        resp = await self.client.get(
            f"{settings.CATALOG_API_BASE_URL}/api/v1/persons/search",
            params={
                "query": query,
                "page_number": self.DEFAULT_PAGE_NUMBER,
                "page_size": self.SEARCH_PAGE_SIZE,
            },
            headers={"Authorization": authorization},
        )
        resp.raise_for_status()
        return resp.json()

    async def person_details(self, person_id: str, authorization: str) -> dict:
        resp = await self.client.get(
            f"{settings.CATALOG_API_BASE_URL}/api/v1/persons/{person_id}",
            headers={"Authorization": authorization},
        )
        resp.raise_for_status()
        return resp.json()
