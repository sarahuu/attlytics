from typing import Any

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.heartbeat import Heartbeat


async def ingest(db: AsyncSession, rows: list[dict[str, Any]]) -> tuple[int, int]:
    if not rows:
        return 0, 0

    stmt = pg_insert(Heartbeat).values(rows)
    stmt = stmt.on_conflict_do_nothing(index_elements=["local_id", "device_id"])
    result = await db.execute(stmt)
    await db.commit()

    received = result.rowcount or 0
    skipped = len(rows) - received
    return received, skipped
