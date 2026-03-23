from typing import Any, Dict, List, Optional

from core.settings import settings
from domain.ports.repository import ReadOnlyRepository

from .base import ESRepositoryBase

DEFAULT_SORT = [{"imdb_rating": {"order": "desc", "missing": "_last"}}]


class FilmESRepository(ESRepositoryBase, ReadOnlyRepository):
    def __init__(self, es):
        super().__init__(es, settings.ES_INDEX_FILMS)

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
        es_sort = []
        if sort:
            order = "desc" if sort.startswith("-") else "asc"
            field = sort.lstrip("+-")
            es_sort.append({field: {"order": order, "missing": "_last"}})
        if not es_sort:
            es_sort = DEFAULT_SORT

        must = []
        if filters and (genre := filters.get("genre")):
            must.append({"terms": {"genre": [genre]}})
        query = {"bool": {"must": must}} if must else {"match_all": {}}

        return await self._search(
            query,
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
            "bool": {
                "should": [
                    {"match_phrase": {"title": {"query": query, "boost": 20}}},
                    {"match_phrase": {"original_title": {"query": query, "boost": 18}}},
                    {"match_phrase": {"title_aliases": {"query": query, "boost": 22}}},
                    {
                        "multi_match": {
                            "query": query,
                            "type": "best_fields",
                            "operator": "and",
                            "fields": [
                                "title^10",
                                "original_title^8",
                                "title_aliases^12",
                                "directors^3",
                                "actors^2",
                            ],
                            "boost": 6,
                        }
                    },
                    {
                        "multi_match": {
                            "query": query,
                            "type": "best_fields",
                            "fields": [
                                "title^4",
                                "original_title^4",
                                "title_aliases^5",
                                "description",
                                "directors^2",
                                "actors",
                            ],
                            "fuzziness": "AUTO",
                            "boost": 2,
                        }
                    },
                    {
                        "match": {
                            "description": {
                                "query": query,
                                "operator": "and",
                                "boost": 0.5,
                            }
                        }
                    },
                ],
                "minimum_should_match": 1,
            }
        }
        return await self._search(
            es_query,
            sort=[{"_score": {"order": "desc"}}, *DEFAULT_SORT],
            page_number=page_number,
            page_size=page_size,
            source=source,
        )
