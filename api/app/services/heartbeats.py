from sqlalchemy.ext.asyncio import AsyncSession

from app.repos import heartbeats as repo
from app.schemas.heartbeat import HeartbeatCreate


async def ingest_heartbeats(
    db: AsyncSession, payloads: list[HeartbeatCreate]
) -> tuple[int, int]:
    if not payloads:
        return 0, 0

    rows = [payload.model_dump() for payload in payloads]
    return await repo.ingest(db, rows)
