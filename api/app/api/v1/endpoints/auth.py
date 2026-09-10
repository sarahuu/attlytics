from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.dependencies import get_optional_token_payload
from app.core.exceptions import UnauthorizedError
from app.db.session import get_db
from app.models.users import User
from app.schemas.auth import Token, UserCreate, UserLogin, UserOut
from app.services import auth as service

router = APIRouter(tags=["auth"])
settings = get_settings()


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    """Store the refresh token in an HttpOnly cookie (never readable by JS)."""
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=refresh_token,
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        path=settings.refresh_cookie_path,
        httponly=True,
        secure=settings.refresh_cookie_secure,
        samesite=settings.refresh_cookie_samesite,
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.refresh_cookie_name,
        path=settings.refresh_cookie_path,
        httponly=True,
        secure=settings.refresh_cookie_secure,
        samesite=settings.refresh_cookie_samesite,
    )


@router.post(
    "/register",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new user account",
)
async def register(payload: UserCreate, db: AsyncSession = Depends(get_db)) -> User:
    return await service.register_user(db, payload)


@router.post(
    "/login",
    response_model=Token,
    summary="Log in; refresh token is set as an HttpOnly cookie",
)
async def login(
    payload: UserLogin,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> Token:
    user = await service.authenticate(db, payload)
    access_token, refresh_token = service.issue_tokens(user)
    _set_refresh_cookie(response, refresh_token)
    return Token(access_token=access_token)


@router.post(
    "/refresh",
    response_model=Token,
    summary="Rotate the refresh cookie and return a new access token",
)
async def refresh(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> Token:
    refresh_token = request.cookies.get(settings.refresh_cookie_name)
    if not refresh_token:
        raise UnauthorizedError("No refresh token")

    access_token, new_refresh_token = await service.refresh_tokens(db, refresh_token)
    _set_refresh_cookie(response, new_refresh_token)
    return Token(access_token=access_token)


@router.post("/logout", summary="Revoke the refresh cookie and access token")
async def logout(
    request: Request,
    response: Response,
    access_payload: dict | None = Depends(get_optional_token_payload),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    await service.logout(
        db,
        refresh_token=request.cookies.get(settings.refresh_cookie_name),
        access_payload=access_payload,
    )
    _clear_refresh_cookie(response)
    return {"detail": "Logged out"}
