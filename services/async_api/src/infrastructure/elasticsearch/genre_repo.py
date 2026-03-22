from typing import Any, Dict, List, Optional

from core.settings import settings
from domain.ports.repository import ReadOnlyRepository

from .base import ESRepositoryBase


class GenreESRepository(ESRepositoryBase, ReadOnlyRepository):
    def __init__(self, es):
        super().__init__(es, settings.ES_INDEX_GENRES)

    async def get_by_id(self, entity_id: str):
        return await self._get(entity_id)

    async def list(
        self,
        *,
        sort: Optional[str],
        page_number: int,
        page_size: int,
        filters: Optional[Dict[str, Any]] = None,
        source: Optional[List[str]] = None,
    ):
        es_sort = None
        return await self._search(
            {"match_all": {}},
            sort=es_sort,
            page_number=page_number,
            page_size=page_size,
            source=source,
        )

    async def search(
        self,
        query: str,
        *,
        sort: Optional[str],
        page_number: int,
        page_size: int,
        source: Optional[List[str]] = None,
    ):
        es_query = {
            "multi_match": {
                "query": query,
                "fields": ["name^4", "aliases^5"],
                "fuzziness": "AUTO",
            }
        }
        return await self._search(
            es_query,
            page_number=page_number,
            page_size=page_size,
            source=source,
        )
