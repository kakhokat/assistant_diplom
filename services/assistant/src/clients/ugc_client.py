from __future__ import annotations

from urllib.parse import quote

import httpx

from core.settings import settings


class UgcClient:
    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    async def bookmarks_by_user(self, user_id: str, authorization: str) -> list[dict]:
        url = (
            f"{settings.UGC_API_BASE_URL}/bookmarks/by-user"
            f"?user_id={quote(user_id)}&limit=50&offset=0"
        )
        resp = await self.client.get(url, headers={'Authorization': authorization})
        resp.raise_for_status()
        return resp.json()

    async def likes_by_user(self, user_id: str, authorization: str) -> list[dict]:
        url = (
            f"{settings.UGC_API_BASE_URL}/likes/by-user"
            f"?user_id={quote(user_id)}&limit=50&offset=0"
        )
        resp = await self.client.get(url, headers={'Authorization': authorization})
        resp.raise_for_status()
        return resp.json()
