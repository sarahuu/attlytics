from fastapi import APIRouter, Depends

from app.core.dependencies import get_current_user
from app.models.users import User
from app.schemas.auth import UserOut

router = APIRouter(tags=["users"])


@router.get("/me", response_model=UserOut, summary="Return the current user")
async def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user
