from __future__ import annotations

import httpx

from core.settings import settings


class UgcClient:
    USER_ACTIVITY_LIMIT = 50
    USER_ACTIVITY_OFFSET = 0

    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    async def bookmarks_by_user(self, user_id: str, authorization: str) -> list[dict]:
        resp = await self.client.get(
            f"{settings.UGC_API_BASE_URL}/bookmarks/by-user",
            params={
                "user_id": user_id,
                "limit": self.USER_ACTIVITY_LIMIT,
                "offset": self.USER_ACTIVITY_OFFSET,
            },
            headers={"Authorization": authorization},
        )
        resp.raise_for_status()
        return resp.json()

    async def likes_by_user(self, user_id: str, authorization: str) -> list[dict]:
        resp = await self.client.get(
            f"{settings.UGC_API_BASE_URL}/likes/by-user",
            params={
                "user_id": user_id,
                "limit": self.USER_ACTIVITY_LIMIT,
                "offset": self.USER_ACTIVITY_OFFSET,
            },
            headers={"Authorization": authorization},
        )
        resp.raise_for_status()
        return resp.json()
