from functools import lru_cache
from typing import Any, Dict, List, Optional

from elasticsearch import AsyncElasticsearch
from fastapi import Depends
from redis.asyncio import Redis

from core.settings import settings
from db.elastic import get_elastic
from db.redis import get_redis
from domain.models.film import Film, FilmListItem
from domain.ports.cache import Cache
from domain.ports.repository import ReadOnlyRepository
from infrastructure.elasticsearch.film_repo import FilmESRepository
from infrastructure.redis.cache import RedisCache, dumps, loads

FILM_CACHE_EXPIRE_IN_SECONDS = settings.FILM_CACHE_TTL


def _cache_key(prefix: str, params: Dict[str, Any]) -> str:
    items = sorted((k, str(v)) for k, v in params.items() if v is not None)
    return prefix + ":" + "|".join(f"{k}={v}" for k, v in items)


class FilmService:
    def __init__(self, repo: ReadOnlyRepository, cache: Cache | None = None):
        self.repo = repo
        self.cache = cache

    async def get_by_id(self, film_id: str) -> Optional[Film]:
        if self.cache:
            raw = await self.cache.get(f"film:{film_id}")
            if raw:
                try:
                    return Film.parse_raw(raw)
                except Exception:
                    pass

        src = await self.repo.get_by_id(film_id)
        if not src:
            return None
        film = Film(**src)

        if self.cache:
            await self.cache.set(
                f"film:{film.id}",
                film.json().encode("utf-8"),
                FILM_CACHE_EXPIRE_IN_SECONDS,
            )
        return film

    async def list_films(
        self,
        *,
        sort: Optional[str],
        page_number: int,
        page_size: int,
        genre: Optional[str] = None,
    ) -> List[FilmListItem]:
        key = _cache_key(
            "films:list",
            {
                "sort": sort,
                "page_number": page_number,
                "page_size": page_size,
                "genre": genre,
            },
        )
        if self.cache:
            raw = await self.cache.get(key)
            if raw:
                try:
                    data = loads(raw)
                    return [FilmListItem(**i) for i in data]
                except Exception:
                    pass

        rows = await self.repo.list(
            sort=sort,
            page_number=page_number,
            page_size=page_size,
            filters={"genre": genre} if genre else None,
            source=["id", "title", "original_title", "title_aliases", "imdb_rating", "description", "genre", "directors"],
        )
        items = [
            FilmListItem(
                uuid=r.get("id", ""),
                title=r.get("title", ""),
                original_title=r.get("original_title"),
                title_aliases=r.get("title_aliases"),
                imdb_rating=r.get("imdb_rating"),
                description=r.get("description"),
                genre=r.get("genre"),
                directors=r.get("directors"),
            )
            for r in rows
        ]
        if self.cache:
            await self.cache.set(
                key,
                dumps([i.dict() for i in items]),
                FILM_CACHE_EXPIRE_IN_SECONDS,
            )
        return items

    async def search_films(
        self,
        *,
        query_str: str,
        page_number: int,
        page_size: int,
    ) -> List[FilmListItem]:
        key = _cache_key(
            "films:search",
            {
                "q": query_str,
                "page_number": page_number,
                "page_size": page_size,
            },
        )
        if self.cache:
            raw = await self.cache.get(key)
            if raw:
                try:
                    data = loads(raw)
                    return [FilmListItem(**i) for i in data]
                except Exception:
                    pass

        rows = await self.repo.search(
            query=query_str,
            sort="-imdb_rating",
            page_number=page_number,
            page_size=page_size,
            source=["id", "title", "original_title", "title_aliases", "imdb_rating", "description", "genre", "directors"],
        )
        items = [
            FilmListItem(
                uuid=r.get("id", ""),
                title=r.get("title", ""),
                original_title=r.get("original_title"),
                title_aliases=r.get("title_aliases"),
                imdb_rating=r.get("imdb_rating"),
                description=r.get("description"),
                genre=r.get("genre"),
                directors=r.get("directors"),
            )
            for r in rows
        ]
        if self.cache:
            await self.cache.set(
                key,
                dumps([i.dict() for i in items]),
                FILM_CACHE_EXPIRE_IN_SECONDS,
            )
        return items


@lru_cache()
def get_film_service(
    redis: Redis = Depends(get_redis),
    elastic: AsyncElasticsearch = Depends(get_elastic),
) -> FilmService:
    repo = FilmESRepository(elastic)
    cache = RedisCache(redis) if redis else None
    return FilmService(repo=repo, cache=cache)
