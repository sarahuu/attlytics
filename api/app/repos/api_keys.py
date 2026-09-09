from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import or_, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.users import UserApiKey


async def create(
    db: AsyncSession, *, user_id: UUID, key_hash: str, device_id: UUID | None = None
) -> UserApiKey:
    row = UserApiKey(user_id=user_id, key_hash=key_hash, device_id=device_id)
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def revoke_active_for_device(
    db: AsyncSession, *, user_id: UUID, device_id: UUID
) -> None:
    """Revoke a device's current keys plus any legacy user-level keys."""
    await db.execute(
        update(UserApiKey)
        .where(
            UserApiKey.user_id == user_id,
            UserApiKey.revoked_at.is_(None),
            or_(UserApiKey.device_id.is_(None), UserApiKey.device_id == device_id),
        )
        .values(revoked_at=datetime.now(UTC))
    )
    await db.commit()
