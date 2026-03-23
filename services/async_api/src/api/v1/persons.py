from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from core.pagination import PaginationParams
from domain.models.person import Person, PersonListItem
from services.person import PersonService, get_person_service

router = APIRouter()


@router.get("/", response_model=List[PersonListItem], summary="List persons")
async def persons_list(
    pagination: PaginationParams = Depends(),
    service: PersonService = Depends(get_person_service),
) -> List[PersonListItem]:
    return await service.list_persons(
        page_number=pagination.page_number, page_size=pagination.page_size
    )


@router.get("/search", response_model=List[PersonListItem], summary="Search persons")
async def persons_search(
    query: str = Query(min_length=1),
    pagination: PaginationParams = Depends(),
    service: PersonService = Depends(get_person_service),
) -> List[PersonListItem]:
    return await service.search_persons(
        query=query,
        page_number=pagination.page_number,
        page_size=pagination.page_size,
    )


@router.get("/{person_id}", response_model=Person, summary="Person details")
async def person_details(
    person_id: UUID, service: PersonService = Depends(get_person_service)
) -> Person:
    person = await service.get_by_id(str(person_id))
    if not person:
        raise HTTPException(status_code=404, detail="person not found")
    return person
