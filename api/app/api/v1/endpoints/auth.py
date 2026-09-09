from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_token_payload
from app.db.session import get_db
from app.models.users import User
from app.schemas.auth import (
    RefreshTokenRequest,
    Token,
    UserCreate,
    UserLogin,
    UserOut,
)
from app.services import auth as service

router = APIRouter(tags=["auth"])


@router.post(
    "/register",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new user account",
)
async def register(payload: UserCreate, db: AsyncSession = Depends(get_db)) -> User:
    return await service.register_user(db, payload)


@router.post("/login", response_model=Token, summary="Exchange credentials for JWT tokens")
async def login(payload: UserLogin, db: AsyncSession = Depends(get_db)) -> Token:
    user = await service.authenticate(db, payload)
    access_token, refresh_token = service.issue_tokens(user)
    return Token(access_token=access_token, refresh_token=refresh_token)


@router.post(
    "/refresh",
    response_model=Token,
    summary="Refresh an expired access token",
)
async def refresh(
    payload: RefreshTokenRequest, db: AsyncSession = Depends(get_db)
) -> Token:
    access_token, refresh_token = await service.refresh_tokens(
        db, payload.refresh_token
    )
    return Token(access_token=access_token, refresh_token=refresh_token)


@router.post("/logout", summary="Revoke the current access token")
async def logout(
    current_user: User = Depends(get_current_user),
    payload: dict = Depends(get_token_payload),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    await service.logout(db, payload)
    return {"detail": "Logged out"}
