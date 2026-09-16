from datetime import datetime, timedelta, timezone
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.heartbeat import Session
from app.repos.sessions import ActivityRepository
from app.schemas.session import ApplicationStat, SessionOut, SessionPage, StatsSummary

DEFAULT_WINDOW_HOURS = 24
MAX_WINDOW_DAYS = 366

PAGE_SIZE = 50
MAX_PAGE_SIZE = 200
MAX_APPLICATIONS = 100


def _as_utc(value: datetime) -> datetime:
    """Treat a naive datetime as UTC so comparisons never mix aware/naive."""
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def resolve_window(
    start: datetime | None,
    end: datetime | None,
    default_hours: int = DEFAULT_WINDOW_HOURS,
) -> tuple[datetime, datetime]:
    """Resolve an explicit window, defaulting the end to now and rejecting bad ranges."""

    resolved_end = _as_utc(end) if end is not None else datetime.now(timezone.utc)
    resolved_start = (
        _as_utc(start)
        if start is not None
        else resolved_end - timedelta(hours=default_hours)
    )

    if resolved_start >= resolved_end:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="start must be before end",
        )

    if resolved_end - resolved_start > timedelta(days=MAX_WINDOW_DAYS):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"window must not exceed {MAX_WINDOW_DAYS} days",
        )

    return resolved_start, resolved_end


def resolve_timezone(name: str) -> str:
    """Validate an IANA timezone name; buckets are wrong silently if this is bogus."""

    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown timezone: {name}",
        )

    return name


def _encode_cursor(session: Session) -> str:
    return f"{session.start_time.isoformat()}|{session.id}"


def _decode_cursor(cursor: str) -> tuple[datetime, UUID]:
    try:
        raw_start, raw_id = cursor.split("|", 1)
        return _as_utc(datetime.fromisoformat(raw_start)), UUID(raw_id)
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid cursor",
        )


async def list_sessions(
    db: AsyncSession,
    user_id: UUID,
    *,
    start: datetime | None = None,
    end: datetime | None = None,
    application: str | None = None,
    device_id: UUID | None = None,
    source: str | None = None,
    cursor: str | None = None,
    limit: int = PAGE_SIZE,
) -> SessionPage:

    window_start, window_end = resolve_window(start, end)
    limit = max(1, min(limit, MAX_PAGE_SIZE))

    repository = ActivityRepository(db)

    rows = await repository.list_sessions(
        user_id,
        window_start,
        window_end,
        application=application,
        device_id=device_id,
        source=source,
        cursor=_decode_cursor(cursor) if cursor else None,
        limit=limit + 1,
    )

    has_more = len(rows) > limit
    items = rows[:limit]

    return SessionPage(
        items=[SessionOut.model_validate(item) for item in items],
        next_cursor=_encode_cursor(items[-1]) if has_more and items else None,
    )


async def get_session(
    db: AsyncSession,
    user_id: UUID,
    session_id: UUID,
) -> SessionOut:

    session = await ActivityRepository(db).get_session(user_id, session_id)

    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    return SessionOut.model_validate(session)


async def summary(
    db: AsyncSession,
    user_id: UUID,
    *,
    start: datetime | None = None,
    end: datetime | None = None,
    tz: str = "UTC",
    device_id: UUID | None = None,
) -> StatsSummary:

    window_start, window_end = resolve_window(start, end)
    tz = resolve_timezone(tz)

    row = await ActivityRepository(db).summarize_sessions(
        user_id,
        window_start,
        window_end,
        tz,
        device_id=device_id,
    )

    total_seconds = float(row.total_seconds or 0)
    active_days = int(row.active_days or 0)

    return StatsSummary(
        total_seconds=total_seconds,
        session_count=int(row.session_count or 0),
        active_days=active_days,
        average_seconds_per_active_day=(
            total_seconds / active_days if active_days else 0.0
        ),
        longest_session_seconds=float(row.longest_session_seconds or 0),
        first_activity=row.first_activity,
        last_activity=row.last_activity,
    )


async def applications(
    db: AsyncSession,
    user_id: UUID,
    *,
    start: datetime | None = None,
    end: datetime | None = None,
    device_id: UUID | None = None,
    limit: int = 20,
) -> list[ApplicationStat]:

    window_start, window_end = resolve_window(start, end)
    limit = max(1, min(limit, MAX_APPLICATIONS))

    repository = ActivityRepository(db)

    rows = await repository.time_per_application(
        user_id,
        window_start,
        window_end,
        device_id=device_id,
        limit=limit,
    )

    range_total = await repository.total_duration(
        user_id,
        window_start,
        window_end,
        device_id=device_id,
    )

    return [
        ApplicationStat(
            application=row.application,
            total_seconds=float(row.total_seconds or 0),
            session_count=int(row.session_count or 0),
            share_percent=(
                round(float(row.total_seconds or 0) / range_total * 100, 2)
                if range_total
                else 0.0
            ),
        )
        for row in rows
    ]
