from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Response, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from ..auth import CurrentUserId, get_current_user_id
from ..deps import db_dep
from ..models.review import ReviewCreate, ReviewOut, ReviewUpdate
from ..repositories.reviews_repo import ReviewsRepo

router = APIRouter(
    prefix="/reviews",
    tags=["reviews"],
    dependencies=[Depends(get_current_user_id)],
)

DbDep = Annotated[AsyncIOMotorDatabase, Depends(db_dep)]
FilmId = Annotated[str, Query(min_length=1, max_length=128)]
ReviewId = Annotated[str, Query(min_length=1)]
Limit = Annotated[int, Query(ge=1, le=200)]
Offset = Annotated[int, Query(ge=0)]
UpdateBody = Annotated[ReviewUpdate, Body()]
REVIEW_NOT_FOUND = "review_not_found"


@router.post("", status_code=201, response_model=ReviewOut)
async def create_review(
    payload: ReviewCreate,
    db: DbDep,
    current_user_id: CurrentUserId,
) -> dict:
    if payload.user_id != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="user_id_mismatch",
        )

    repo = ReviewsRepo(db)
    return await repo.create(
        payload.film_id,
        current_user_id,
        payload.text,
        payload.user_film_rating,
    )


@router.get("", response_model=ReviewOut)
async def get_review(
    review_id: ReviewId,
    db: DbDep,
) -> dict:
    repo = ReviewsRepo(db)
    doc = await repo.get(review_id)
    if not doc:
        raise HTTPException(status_code=404, detail=REVIEW_NOT_FOUND)
    return doc


@router.put("", response_model=ReviewOut)
async def update_review(
    review_id: ReviewId,
    payload: UpdateBody,
    db: DbDep,
    current_user_id: CurrentUserId,
) -> dict:
    repo = ReviewsRepo(db)

    existing = await repo.get(review_id)
    if not existing:
        raise HTTPException(status_code=404, detail=REVIEW_NOT_FOUND)

    owner = existing.get("user_id")
    if owner != current_user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")

    doc = await repo.update(review_id, payload.text, payload.user_film_rating)
    if not doc:
        raise HTTPException(status_code=404, detail=REVIEW_NOT_FOUND)
    return doc


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_review(
    review_id: ReviewId,
    db: DbDep,
    current_user_id: CurrentUserId,
) -> Response:
    repo = ReviewsRepo(db)

    existing = await repo.get(review_id)
    if not existing:
        raise HTTPException(status_code=404, detail=REVIEW_NOT_FOUND)

    owner = existing.get("user_id")
    if owner != current_user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")

    ok = await repo.delete(review_id)
    if not ok:
        raise HTTPException(status_code=404, detail=REVIEW_NOT_FOUND)

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/by-film", response_model=list[ReviewOut])
async def list_reviews_by_film(
    film_id: FilmId,
    db: DbDep,
    limit: Limit = 50,
    offset: Offset = 0,
) -> list[dict]:
    repo = ReviewsRepo(db)
    return await repo.list_by_film(film_id, limit, offset)
