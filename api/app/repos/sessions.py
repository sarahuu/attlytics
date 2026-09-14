from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, tuple_, update
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

    async def get_existing_sessions(
        self,
        keys: list[tuple[UUID, UUID, UUID]],  # (user_id, device_id, state_id)
    ) -> dict[tuple[UUID, UUID, UUID], Session]:

        if not keys:
            return {}

        result = await self.db.execute(
            select(Session).where(
                tuple_(
                    Session.user_id,
                    Session.device_id,
                    Session.state_id,
                ).in_(keys)
            )
        )

        return {
            (s.user_id, s.device_id, s.state_id): s
            for s in result.scalars().all()
        }

    async def create_session(
        self,
        session: Session,
    ) -> Session:

        self.db.add(session)

        await self.db.flush()

        return session


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