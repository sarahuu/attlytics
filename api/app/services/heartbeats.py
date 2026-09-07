from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models.heartbeat import Heartbeat
from app.schemas.heartbeat import HeartbeatCreate


def ingest_heartbeats(
    db: Session, payloads: list[HeartbeatCreate]
) -> tuple[int, int]:
    if not payloads:
        return 0, 0

    rows = [payload.model_dump() for payload in payloads]

    stmt = pg_insert(Heartbeat).values(rows)
    stmt = stmt.on_conflict_do_nothing(index_elements=["local_id"])
    result = db.execute(stmt)
    db.commit()

    received = result.rowcount or 0
    skipped = len(rows) - received
    return received, skipped
