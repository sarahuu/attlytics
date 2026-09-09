from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import SecurityUtils
from app.db.session import get_db
from app.models.users import User
from app.repos import tokens as token_repo
from app.repos import users as user_repo

bearer_scheme = HTTPBearer(auto_error=False)

_UNAUTHORIZED = {
    "status_code": status.HTTP_401_UNAUTHORIZED,
    "headers": {"WWW-Authenticate": "Bearer"},
}


async def get_token_payload(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Verify the bearer access token and return its payload.

    Rejects missing, invalid, expired, and revoked (denylisted ``jti``) tokens.
    """
    if credentials is None:
        raise HTTPException(detail="Not authenticated", **_UNAUTHORIZED)

    try:
        payload = SecurityUtils.verify_token(
            credentials.credentials, expected_type="access"
        )
    except ValueError:
        raise HTTPException(detail="Invalid or expired token", **_UNAUTHORIZED)

    if await token_repo.is_revoked(db, payload["jti"]):
        raise HTTPException(detail="Token has been revoked", **_UNAUTHORIZED)

    return payload


async def get_current_user(
    payload: dict = Depends(get_token_payload),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Resolve the authenticated user from the verified token payload."""
    try:
        user_id = UUID(payload["sub"])
    except (KeyError, ValueError):
        raise HTTPException(detail="Invalid token payload", **_UNAUTHORIZED)

    user = await user_repo.get_by_id(db, user_id)
    if user is None:
        raise HTTPException(detail="User no longer exists", **_UNAUTHORIZED)
    return user
