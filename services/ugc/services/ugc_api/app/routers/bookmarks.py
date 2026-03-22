from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Query
from fastapi import Response
from fastapi import status
from motor.motor_asyncio import AsyncIOMotorDatabase

from ..auth import CurrentUserId
from ..auth import get_current_user_id
from ..deps import db_dep
from ..models.bookmark import BookmarkCreate
from ..models.bookmark import BookmarkOut
from ..repositories.bookmarks_repo import BookmarksRepo

router = APIRouter(
    prefix="/bookmarks",
    tags=["bookmarks"],
    dependencies=[Depends(get_current_user_id)],
)

DbDep = Annotated[AsyncIOMotorDatabase, Depends(db_dep)]
UserId = Annotated[str, Query(min_length=1, max_length=128)]
FilmId = Annotated[str, Query(min_length=1, max_length=128)]
Limit = Annotated[int, Query(ge=1, le=200)]
Offset = Annotated[int, Query(ge=0)]


@router.put("", response_model=BookmarkOut)
async def upsert_bookmark(
    payload: BookmarkCreate,
    db: DbDep,
    current_user_id: CurrentUserId,
) -> dict:
    # не доверяем user_id из тела
    if payload.user_id != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="user_id_mismatch",
        )

    repo = BookmarksRepo(db)
    return await repo.create(current_user_id, payload.film_id)


@router.get("", response_model=BookmarkOut)
async def get_bookmark(
    user_id: UserId,
    film_id: FilmId,
    db: DbDep,
    current_user_id: CurrentUserId,
) -> dict:
    if user_id != current_user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")

    repo = BookmarksRepo(db)
    doc = await repo.get(current_user_id, film_id)
    if not doc:
        raise HTTPException(status_code=404, detail="bookmark_not_found")
    return doc


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_bookmark(
    user_id: UserId,
    film_id: FilmId,
    db: DbDep,
    current_user_id: CurrentUserId,
) -> Response:
    if user_id != current_user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")

    repo = BookmarksRepo(db)
    ok = await repo.delete(current_user_id, film_id)
    if not ok:
        raise HTTPException(status_code=404, detail="bookmark_not_found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/by-user", response_model=list[BookmarkOut])
async def list_bookmarks_by_user(
    user_id: UserId,
    db: DbDep,
    current_user_id: CurrentUserId,
    limit: Limit = 50,
    offset: Offset = 0,
) -> list[dict]:
    if user_id != current_user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")

    repo = BookmarksRepo(db)
    return await repo.list_by_user(current_user_id, limit, offset)
