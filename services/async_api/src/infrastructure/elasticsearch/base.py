from typing import Any, Dict, List, Optional

from elasticsearch import AsyncElasticsearch, NotFoundError, TransportError
from fastapi import HTTPException


class ESRepositoryBase:
    def __init__(self, es: AsyncElasticsearch, index: str):
        self.es = es
        self.index = index

    async def _get(self, entity_id: str) -> Optional[Dict[str, Any]]:
        try:
            doc = await self.es.get(index=self.index, id=entity_id)
        except NotFoundError:
            return None
        except TransportError as exc:
            raise HTTPException(
                status_code=503, detail="Elasticsearch is unavailable"
            ) from exc
        src = doc.get("_source", {})
        src.setdefault("id", doc.get("_id"))
        return src

    async def _search(
        self,
        query: Dict[str, Any],
        *,
        sort: Optional[List[Dict[str, Any]]] = None,
        page_number: int = 1,
        page_size: int = 50,
        source: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        from_ = (page_number - 1) * page_size
        try:
            resp = await self.es.search(
                index=self.index,
                query=query,
                sort=sort,
                from_=from_,
                size=page_size,
                _source=source,
            )
        except NotFoundError:
            return []
        except TransportError as exc:
            raise HTTPException(
                status_code=503, detail="Elasticsearch is unavailable"
            ) from exc
        hits = resp.get("hits", {}).get("hits", [])
        return [h.get("_source", {}) for h in hits]
