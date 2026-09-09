from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, UnauthorizedError
from app.core.security import SecurityUtils
from app.models.users import User
from app.repos import tokens as token_repo
from app.repos import users as repo
from app.schemas.auth import UserCreate, UserLogin


def _expires_at(payload: dict) -> datetime:
    return datetime.fromtimestamp(payload["exp"], tz=timezone.utc)


async def register_user(db: AsyncSession, payload: UserCreate) -> User:
    email = payload.email.lower()

    if await repo.get_by_email(db, email) is not None:
        raise ConflictError("Email already registered")

    try:
        return await repo.create(
            db,
            first_name=payload.first_name,
            last_name=payload.last_name,
            email=email,
            password_hash=SecurityUtils.get_password_hash(payload.password),
        )
    except IntegrityError:
        await db.rollback()
        raise ConflictError("Email already registered") from None


async def authenticate(db: AsyncSession, payload: UserLogin) -> User:
    user = await repo.get_by_email(db, payload.email.lower())
    if user is None or not SecurityUtils.verify_password(
        payload.password, user.password_hash
    ):
        raise UnauthorizedError("Incorrect email or password")
    return user


def issue_tokens(user: User) -> tuple[str, str]:
    """Return ``(access_token, refresh_token)`` for a user."""
    return (
        SecurityUtils.create_access_token(user.id),
        SecurityUtils.create_refresh_token(user.id),
    )


async def refresh_tokens(db: AsyncSession, refresh_token: str) -> tuple[str, str]:
    try:
        payload = SecurityUtils.verify_token(refresh_token, expected_type="refresh")
        user_id = UUID(payload["sub"])
    except (ValueError, KeyError):
        raise UnauthorizedError("Invalid or expired refresh token") from None

    if await token_repo.is_revoked(db, payload["jti"]):
        raise UnauthorizedError("Refresh token has been revoked")

    user = await repo.get_by_id(db, user_id)
    if user is None:
        raise UnauthorizedError("User no longer exists")

    new_access, new_refresh = issue_tokens(user)

    await token_repo.revoke(
        db,
        jti=payload["jti"],
        user_id=user.id,
        expires_at=_expires_at(payload),
    )
    return new_access, new_refresh


async def logout(db: AsyncSession, payload: dict) -> None:
    """Revoke the presented token so it can't be reused."""
    try:
        user_id = UUID(payload["sub"]) if payload.get("sub") else None
    except ValueError:
        user_id = None
    await token_repo.revoke(
        db,
        jti=payload["jti"],
        user_id=user_id,
        expires_at=_expires_at(payload),
    )
