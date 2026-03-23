from functools import lru_cache
from typing import List, Optional

from elasticsearch import AsyncElasticsearch
from fastapi import Depends
from infrastructure.elasticsearch.genre_repo import GenreESRepository
from redis.asyncio import Redis

from core.settings import settings
from db.elastic import get_elastic
from db.redis import get_redis
from domain.models.genre import Genre, GenreListItem
from domain.ports.cache import Cache
from domain.ports.repository import ReadOnlyRepository
from infrastructure.redis.cache import RedisCache, dumps, loads

GENRE_CACHE_TTL = settings.GENRE_CACHE_TTL


class GenreService:
    def __init__(self, repo: ReadOnlyRepository, cache: Cache | None = None):
        self.repo = repo
        self.cache = cache

    async def get_by_id(self, genre_id: str) -> Optional[Genre]:
        key = f"genre:{genre_id}"
        if self.cache:
            raw = await self.cache.get(key)
            if raw:
                try:
                    return Genre.parse_raw(raw)
                except Exception:
                    pass
        src = await self.repo.get_by_id(genre_id)
        if not src:
            return None
        genre = Genre(**src)
        if self.cache:
            await self.cache.set(key, genre.json().encode("utf-8"), GENRE_CACHE_TTL)
        return genre

    async def list_genres(
        self, *, page_number: int, page_size: int
    ) -> List[GenreListItem]:
        key = f"genres:list:p{page_number}:s{page_size}"
        if self.cache:
            raw = await self.cache.get(key)
            if raw:
                try:
                    data = loads(raw)
                    return [GenreListItem(**i) for i in data]
                except Exception:
                    pass
        rows = await self.repo.list(
            sort=None,
            page_number=page_number,
            page_size=page_size,
            source=["id", "name"],
        )
        items = [
            GenreListItem(uuid=r.get("id", ""), name=r.get("name", "")) for r in rows
        ]
        if self.cache:
            await self.cache.set(key, dumps([i.dict() for i in items]), GENRE_CACHE_TTL)
        return items

    async def search_genres(
        self, *, query: str, page_number: int, page_size: int
    ) -> List[GenreListItem]:
        key = f"genres:search:{query}:p{page_number}:s{page_size}"
        if self.cache:
            raw = await self.cache.get(key)
            if raw:
                try:
                    data = loads(raw)
                    return [GenreListItem(**i) for i in data]
                except Exception:
                    pass
        rows = await self.repo.search(
            query=query,
            sort=None,
            page_number=page_number,
            page_size=page_size,
            source=["id", "name"],
        )
        items = [
            GenreListItem(uuid=r.get("id", ""), name=r.get("name", "")) for r in rows
        ]
        if self.cache:
            await self.cache.set(key, dumps([i.dict() for i in items]), GENRE_CACHE_TTL)
        return items


@lru_cache()
def get_genre_service(
    redis: Redis = Depends(get_redis),
    elastic: AsyncElasticsearch = Depends(get_elastic),
) -> GenreService:
    repo = GenreESRepository(elastic)
    cache = RedisCache(redis) if redis else None
    return GenreService(repo=repo, cache=cache)
