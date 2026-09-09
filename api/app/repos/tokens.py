from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tokens import RevokedToken


async def is_revoked(db: AsyncSession, jti: str) -> bool:
    row = await db.scalar(select(RevokedToken.id).where(RevokedToken.jti == jti))
    return row is not None


async def revoke(
    db: AsyncSession,
    *,
    jti: str,
    user_id: UUID | None = None,
    expires_at: datetime,
) -> None:
    stmt = pg_insert(RevokedToken).values(
        jti=jti, user_id=user_id, expires_at=expires_at
    )
    stmt = stmt.on_conflict_do_nothing(index_elements=["jti"])
    await db.execute(stmt)
    await db.commit()
