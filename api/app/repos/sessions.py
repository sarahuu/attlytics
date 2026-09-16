from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import Float, case, cast, func, literal_column, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.heartbeat import Heartbeat, Session


class ActivityRepository:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_pending_events(
        self,
        limit: int = 100,
    ) -> list[Heartbeat]:

        result = await self.db.execute(
            select(Heartbeat)
            .where(
                Heartbeat.processed_at.is_(None)
            )
            .order_by(
                Heartbeat.device_id,
                Heartbeat.timestamp,
                Heartbeat.id,
            )
            .limit(limit).with_for_update(skip_locked=True)
        )

        return list(result.scalars().all())

    async def upsert_sessions(
        self,
        rows: list[dict[str, Any]],
    ) -> tuple[int, int]:

        if not rows:
            return 0, 0

        stmt = pg_insert(Session).values(rows)

        start_time = func.least(
            Session.start_time, stmt.excluded.start_time
        )
        end_time = func.greatest(
            Session.end_time, stmt.excluded.end_time
        )

        stmt = stmt.on_conflict_do_update(
            index_elements=["user_id", "device_id", "state_id"],
            set_={
                "start_time": start_time,
                "end_time": end_time,
                "duration_seconds": case(
                    (
                        end_time.is_not(None),
                        cast(
                            func.extract(
                                "epoch", end_time - start_time
                            ),
                            Float,
                        ),
                    ),
                    else_=Session.duration_seconds,
                ),
                "updated_at": func.now(),
            },
        ).returning(
            (literal_column("xmax") == 0).label("inserted")
        )

        result = await self.db.execute(stmt)
        flags = list(result.scalars().all())

        created = sum(1 for inserted in flags if inserted)

        return created, len(flags) - created


    async def mark_events_sessionized(
        self,
        event_ids: list[UUID],
    ) -> None:

        if not event_ids:
            return

        now = datetime.now(timezone.utc)

        await self.db.execute(
            update(Heartbeat)
            .where(Heartbeat.id.in_(event_ids))
            .values(processed_at=now)
        )