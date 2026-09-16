from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Float,
    and_,
    case,
    cast,
    distinct,
    func,
    literal_column,
    or_,
    select,
    update,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.heartbeat import Heartbeat, Session


class ActivityRepository:

    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def _session_filters(
        user_id: UUID,
        start: datetime,
        end: datetime,
        *,
        application: str | None = None,
        device_id: UUID | None = None,
        source: str | None = None,
    ) -> list:

        filters = [
            Session.user_id == user_id,
            Session.start_time >= start,
            Session.start_time < end,
        ]

        if application is not None:
            filters.append(Session.application == application)

        if device_id is not None:
            filters.append(Session.device_id == device_id)

        if source is not None:
            filters.append(Session.source == source)

        return filters

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

    async def list_sessions(
        self,
        user_id: UUID,
        start: datetime,
        end: datetime,
        *,
        application: str | None = None,
        device_id: UUID | None = None,
        source: str | None = None,
        cursor: tuple[datetime, UUID] | None = None,
        limit: int = 50,
    ) -> list[Session]:

        filters = self._session_filters(
            user_id,
            start,
            end,
            application=application,
            device_id=device_id,
            source=source,
        )

        if cursor is not None:
            cursor_start, cursor_id = cursor
            filters.append(
                or_(
                    Session.start_time < cursor_start,
                    and_(
                        Session.start_time == cursor_start,
                        Session.id < cursor_id,
                    ),
                )
            )

        result = await self.db.execute(
            select(Session)
            .where(*filters)
            .order_by(
                Session.start_time.desc(),
                Session.id.desc(),
            )
            .limit(limit)
        )

        return list(result.scalars().all())

    async def get_session(
        self,
        user_id: UUID,
        session_id: UUID,
    ) -> Session | None:

        result = await self.db.execute(
            select(Session).where(
                Session.id == session_id,
                Session.user_id == user_id,
            )
        )

        return result.scalar_one_or_none()

    async def summarize_sessions(
        self,
        user_id: UUID,
        start: datetime,
        end: datetime,
        tz: str,
        *,
        device_id: UUID | None = None,
    ):

        local_day = func.date_trunc(
            "day", func.timezone(tz, Session.start_time)
        )

        result = await self.db.execute(
            select(
                func.coalesce(
                    func.sum(Session.duration_seconds), 0.0
                ).label("total_seconds"),
                func.count().label("session_count"),
                func.count(distinct(local_day)).label("active_days"),
                func.max(Session.duration_seconds).label(
                    "longest_session_seconds"
                ),
                func.min(Session.start_time).label("first_activity"),
                func.max(
                    func.coalesce(Session.end_time, Session.start_time)
                ).label("last_activity"),
            ).where(
                *self._session_filters(
                    user_id, start, end, device_id=device_id
                )
            )
        )

        return result.one()

    async def time_per_application(
        self,
        user_id: UUID,
        start: datetime,
        end: datetime,
        *,
        device_id: UUID | None = None,
        limit: int = 20,
    ):

        total_seconds = func.coalesce(
            func.sum(Session.duration_seconds), 0.0
        )

        result = await self.db.execute(
            select(
                Session.application,
                total_seconds.label("total_seconds"),
                func.count().label("session_count"),
            )
            .where(
                *self._session_filters(
                    user_id, start, end, device_id=device_id
                )
            )
            .group_by(Session.application)
            .order_by(total_seconds.desc())
            .limit(limit)
        )

        return list(result.all())

    async def total_duration(
        self,
        user_id: UUID,
        start: datetime,
        end: datetime,
        *,
        device_id: UUID | None = None,
    ) -> float:

        result = await self.db.execute(
            select(
                func.coalesce(func.sum(Session.duration_seconds), 0.0)
            ).where(
                *self._session_filters(
                    user_id, start, end, device_id=device_id
                )
            )
        )

        return float(result.scalar_one())