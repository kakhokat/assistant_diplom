from functools import lru_cache
from typing import List, Optional

from elasticsearch import AsyncElasticsearch
from fastapi import Depends
from redis.asyncio import Redis

from core.settings import settings
from db.elastic import get_elastic
from db.redis import get_redis
from domain.models.person import Person, PersonListItem
from domain.ports.cache import Cache
from domain.ports.repository import ReadOnlyRepository
from infrastructure.elasticsearch.person_repo import PersonESRepository
from infrastructure.redis.cache import RedisCache, dumps, loads

PERSON_CACHE_TTL = settings.PERSON_CACHE_TTL


class PersonService:
    def __init__(self, repo: ReadOnlyRepository, cache: Cache | None = None):
        self.repo = repo
        self.cache = cache

    async def get_by_id(self, person_id: str) -> Optional[Person]:
        key = f"person:{person_id}"
        if self.cache:
            raw = await self.cache.get(key)
            if raw:
                try:
                    return Person.parse_raw(raw)
                except Exception:
                    pass
        src = await self.repo.get_by_id(person_id)
        if not src:
            return None
        person = Person(**src)
        if self.cache:
            await self.cache.set(
                key, person.json().encode("utf-8"), PERSON_CACHE_TTL
            )
        return person

    async def list_persons(
        self, *, page_number: int, page_size: int
    ) -> List[PersonListItem]:
        key = f"persons:list:p{page_number}:s{page_size}"
        if self.cache:
            raw = await self.cache.get(key)
            if raw:
                try:
                    data = loads(raw)
                    return [PersonListItem(**i) for i in data]
                except Exception:
                    pass
        rows = await self.repo.list(
            sort=None,
            page_number=page_number,
            page_size=page_size,
            source=["id", "full_name", "aliases"],
        )
        items = [
            PersonListItem(
                uuid=r.get("id", ""),
                full_name=r.get("full_name", ""),
                aliases=r.get("aliases") or [],
            )
            for r in rows
        ]
        if self.cache:
            await self.cache.set(
                key, dumps([i.dict() for i in items]), PERSON_CACHE_TTL
            )
        return items

    async def search_persons(
        self, *, query: str, page_number: int, page_size: int
    ) -> List[PersonListItem]:
        key = f"persons:search:{query}:p{page_number}:s{page_size}"
        if self.cache:
            raw = await self.cache.get(key)
            if raw:
                try:
                    data = loads(raw)
                    return [PersonListItem(**i) for i in data]
                except Exception:
                    pass
        rows = await self.repo.search(
            query=query,
            sort=None,
            page_number=page_number,
            page_size=page_size,
            source=["id", "full_name", "aliases"],
        )
        items = [
            PersonListItem(
                uuid=r.get("id", ""),
                full_name=r.get("full_name", ""),
                aliases=r.get("aliases") or [],
            )
            for r in rows
        ]
        if self.cache:
            await self.cache.set(
                key, dumps([i.dict() for i in items]), PERSON_CACHE_TTL
            )
        return items


@lru_cache()
def get_person_service(
    redis: Redis = Depends(get_redis),
    elastic: AsyncElasticsearch = Depends(get_elastic),
) -> PersonService:
    repo = PersonESRepository(elastic)
    cache = RedisCache(redis) if redis else None
    return PersonService(repo=repo, cache=cache)
