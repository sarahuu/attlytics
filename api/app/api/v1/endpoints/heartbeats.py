from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

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
def ingest_heartbeats(
    payloads: list[HeartbeatCreate],
    db: Session = Depends(get_db),
) -> HeartbeatIngestResult:
    received, skipped = service.ingest_heartbeats(db, payloads)
    return HeartbeatIngestResult(received=received, skipped=skipped)
