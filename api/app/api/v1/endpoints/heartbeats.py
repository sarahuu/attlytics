from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.heartbeat import HeartbeatCreate, HeartbeatIngestResult
from app.services import heartbeats as service

router = APIRouter(tags=["heartbeats"])


@router.post(
    "",
    response_model=HeartbeatIngestResult,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest a batch of heartbeats pushed from a device",
)
async def ingest_heartbeats(
    payloads: list[HeartbeatCreate],
    db: AsyncSession = Depends(get_db),
) -> HeartbeatIngestResult:
    received, skipped = await service.ingest_heartbeats(db, payloads)
    return HeartbeatIngestResult(received=received, skipped=skipped)
