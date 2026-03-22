from fastapi import APIRouter
from fastapi import Depends
from fastapi import Query

from domain.models.user import LoginHistoryRecord
from domain.models.user import UserProfile
from domain.models.user import UserUpdate
from services.users import UserService
from services.users import get_user_service
from .auth import get_current_user

router = APIRouter()


@router.patch("/me", response_model=UserProfile)
async def update_me(
    payload: UserUpdate,
    current: UserProfile = Depends(get_current_user),
    service: UserService = Depends(get_user_service),
):
    return await service.update_me(current, payload)


@router.get("/me/login-history", response_model=list[LoginHistoryRecord])
async def login_history(
    current: UserProfile = Depends(get_current_user),
    service: UserService = Depends(get_user_service),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    return await service.get_login_history(
        user_id=current.id, limit=limit, offset=offset
    )
