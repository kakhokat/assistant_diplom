from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from ..auth import CurrentUserId, get_current_user_id
from ..deps import db_dep
from ..models.like import LikeAggregatesOut, LikeCreate, LikeOut
from ..repositories.likes_repo import LikesRepo

router = APIRouter(
    prefix="/likes",
    tags=["likes"],
    dependencies=[Depends(get_current_user_id)],
)

DbDep = Annotated[AsyncIOMotorDatabase, Depends(db_dep)]
UserId = Annotated[str, Query(min_length=1, max_length=128)]
FilmId = Annotated[str, Query(min_length=1, max_length=128)]
Limit = Annotated[int, Query(ge=1, le=200)]
Offset = Annotated[int, Query(ge=0)]


@router.put("", response_model=LikeOut)
async def upsert_like(
    payload: LikeCreate,
    db: DbDep,
    current_user_id: CurrentUserId,
) -> dict:
    if payload.user_id != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="user_id_mismatch",
        )

    repo = LikesRepo(db)
    return await repo.upsert(current_user_id, payload.film_id, payload.value)


@router.get("", response_model=LikeOut)
async def get_like(
    user_id: UserId,
    film_id: FilmId,
    db: DbDep,
    current_user_id: CurrentUserId,
) -> dict:
    if user_id != current_user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")

    repo = LikesRepo(db)
    doc = await repo.get(current_user_id, film_id)
    if not doc:
        raise HTTPException(status_code=404, detail="like_not_found")
    return doc


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_like(
    user_id: UserId,
    film_id: FilmId,
    db: DbDep,
    current_user_id: CurrentUserId,
) -> Response:
    if user_id != current_user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")

    repo = LikesRepo(db)
    ok = await repo.delete(current_user_id, film_id)
    if not ok:
        raise HTTPException(status_code=404, detail="like_not_found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/by-user", response_model=list[LikeOut])
async def list_likes_by_user(
    user_id: UserId,
    db: DbDep,
    current_user_id: CurrentUserId,
    limit: Limit = 50,
    offset: Offset = 0,
) -> list[dict]:
    if user_id != current_user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")

    repo = LikesRepo(db)
    return await repo.list_by_user(current_user_id, limit, offset)


@router.get("/aggregates", response_model=LikeAggregatesOut)
async def aggregates_for_film(
    film_id: FilmId,
    db: DbDep,
) -> dict:
    repo = LikesRepo(db)
    return await repo.aggregates_for_film(film_id)
