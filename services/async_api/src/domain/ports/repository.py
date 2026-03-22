from typing import Any, Dict, List, Optional, Protocol


class ReadOnlyRepository(Protocol):
    async def get_by_id(self, entity_id: str) -> Optional[Dict[str, Any]]: ...

    async def list(
        self,
        *,
        sort: Optional[str],
        page_number: int,
        page_size: int,
        filters: Optional[Dict[str, Any]] = None,
        source: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]: ...

    async def search(
        self,
        query: str,
        *,
        sort: Optional[str],
        page_number: int,
        page_size: int,
        source: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]: ...
