from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from core.pagination import PaginationParams
from domain.models.genre import Genre, GenreListItem
from services.genre import GenreService, get_genre_service

router = APIRouter()


@router.get("/", response_model=List[GenreListItem], summary="List genres")
async def genres_list(
    pagination: PaginationParams = Depends(),
    service: GenreService = Depends(get_genre_service),
) -> List[GenreListItem]:
    return await service.list_genres(
        page_number=pagination.page_number, page_size=pagination.page_size
    )


@router.get("/search", response_model=List[GenreListItem], summary="Search genres")
async def genres_search(
    query: str = Query(min_length=1),
    pagination: PaginationParams = Depends(),
    service: GenreService = Depends(get_genre_service),
) -> List[GenreListItem]:
    return await service.search_genres(
        query=query,
        page_number=pagination.page_number,
        page_size=pagination.page_size,
    )


@router.get("/{genre_id}", response_model=Genre, summary="Genre details")
async def genre_details(
    genre_id: UUID, service: GenreService = Depends(get_genre_service)
) -> Genre:
    genre = await service.get_by_id(str(genre_id))
    if not genre:
        raise HTTPException(status_code=404, detail="genre not found")
    return genre
