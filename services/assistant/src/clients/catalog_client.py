from __future__ import annotations

from urllib.parse import quote

import httpx

from core.settings import settings


class CatalogClient:
    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    async def search_films(self, query: str, authorization: str) -> list[dict]:
        url = (
            f"{settings.CATALOG_API_BASE_URL}/api/v1/films/search"
            f"?query={quote(query)}&page_number=1&page_size=10"
        )
        resp = await self.client.get(url, headers={'Authorization': authorization})
        resp.raise_for_status()
        return resp.json()

    async def list_top_films(self, authorization: str, limit: int = 10) -> list[dict]:
        url = (
            f"{settings.CATALOG_API_BASE_URL}/api/v1/films/"
            f"?page_number=1&page_size={limit}&sort=-imdb_rating"
        )
        resp = await self.client.get(url, headers={'Authorization': authorization})
        resp.raise_for_status()
        return resp.json()

    async def film_details(self, film_id: str, authorization: str) -> dict:
        resp = await self.client.get(
            f"{settings.CATALOG_API_BASE_URL}/api/v1/films/{film_id}",
            headers={'Authorization': authorization},
        )
        resp.raise_for_status()
        return resp.json()


    async def search_genres(self, query: str, authorization: str) -> list[dict]:
        url = (
            f"{settings.CATALOG_API_BASE_URL}/api/v1/genres/search"
            f"?query={quote(query)}&page_number=1&page_size=10"
        )
        resp = await self.client.get(url, headers={'Authorization': authorization})
        resp.raise_for_status()
        return resp.json()

    async def genre_details(self, genre_id: str, authorization: str) -> dict:
        resp = await self.client.get(
            f"{settings.CATALOG_API_BASE_URL}/api/v1/genres/{genre_id}",
            headers={'Authorization': authorization},
        )
        resp.raise_for_status()
        return resp.json()

    async def films_by_genre(self, genre_id: str, authorization: str) -> list[dict]:
        url = (
            f"{settings.CATALOG_API_BASE_URL}/api/v1/films/"
            f"?page_number=1&page_size=20&genre={quote(genre_id)}"
        )
        resp = await self.client.get(url, headers={'Authorization': authorization})
        resp.raise_for_status()
        return resp.json()

    async def search_persons(self, query: str, authorization: str) -> list[dict]:
        url = (
            f"{settings.CATALOG_API_BASE_URL}/api/v1/persons/search"
            f"?query={quote(query)}&page_number=1&page_size=10"
        )
        resp = await self.client.get(url, headers={'Authorization': authorization})
        resp.raise_for_status()
        return resp.json()

    async def person_details(self, person_id: str, authorization: str) -> dict:
        resp = await self.client.get(
            f"{settings.CATALOG_API_BASE_URL}/api/v1/persons/{person_id}",
            headers={'Authorization': authorization},
        )
        resp.raise_for_status()
        return resp.json()
