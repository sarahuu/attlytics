from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.users import UserApiKey


async def create(db: AsyncSession, *, user_id: UUID, key_hash: str) -> UserApiKey:
    row = UserApiKey(user_id=user_id, key_hash=key_hash)
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row
