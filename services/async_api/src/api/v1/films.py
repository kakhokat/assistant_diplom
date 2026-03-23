from http import HTTPStatus
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from core.pagination import PaginationParams
from domain.models.film import FilmDetail, FilmListItem
from services.film import FilmService, get_film_service

router = APIRouter()


@router.get("/", response_model=List[FilmListItem], summary="List films")
async def films_list(
    sort: Optional[str] = Query(default="-imdb_rating"),
    genre: Optional[str] = Query(default=None, description="UUID жанра"),
    pagination: PaginationParams = Depends(),
    film_service: FilmService = Depends(get_film_service),
) -> List[FilmListItem]:
    return await film_service.list_films(
        sort=sort,
        page_number=pagination.page_number,
        page_size=pagination.page_size,
        genre=genre,
    )


@router.get("/search", response_model=List[FilmListItem], summary="Search films")
async def films_search(
    query: str = Query(min_length=1),
    pagination: PaginationParams = Depends(),
    film_service: FilmService = Depends(get_film_service),
) -> List[FilmListItem]:
    return await film_service.search_films(
        query_str=query,
        page_number=pagination.page_number,
        page_size=pagination.page_size,
    )


@router.get("/{film_id}", response_model=FilmDetail, summary="Film details")
async def film_details(
    film_id: UUID, film_service: FilmService = Depends(get_film_service)
) -> FilmDetail:
    film = await film_service.get_by_id(str(film_id))
    if not film:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="film not found")
    return FilmDetail(
        uuid=film.id,
        title=film.title,
        original_title=film.original_title,
        title_aliases=film.title_aliases,
        imdb_rating=film.imdb_rating,
        description=film.description,
        genre=film.genre,
        runtime_minutes=film.runtime_minutes,
        directors=film.directors,
        actors=film.actors,
        writers=film.writers,
    )
