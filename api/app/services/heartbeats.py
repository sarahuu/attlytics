from sqlalchemy.ext.asyncio import AsyncSession

from app.models.users import Device
from app.repos import heartbeats as repo
from app.schemas.heartbeat import HeartbeatCreate


async def ingest_heartbeats(
    db: AsyncSession, device: Device, payloads: list[HeartbeatCreate]
) -> tuple[int, int]:
    if not payloads:
        return 0, 0

    rows = []
    for payload in payloads:
        row = payload.model_dump()
        # Bind enums to their plain string values.
        row["source"] = payload.source.value
        row["event_type"] = payload.event_type.value
        row["user_id"] = device.user_id
        row["device_id"] = device.id
        rows.append(row)

    return await repo.ingest(db, rows)
