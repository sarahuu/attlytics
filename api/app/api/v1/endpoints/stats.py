from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.users import User
from app.schemas.session import ApplicationStat, StatsSummary
from app.services import analytics as service

router = APIRouter(tags=["stats"])


@router.get(
    "/summary",
    response_model=StatsSummary,
    summary="Totals over a time window",
)
async def summary(
    start: datetime | None = Query(
        default=None,
        description="Window start (ISO-8601). Defaults to 24h before end.",
    ),
    end: datetime | None = Query(
        default=None,
        description="Window end (ISO-8601). Defaults to now.",
    ),
    tz: str = Query(
        default="UTC",
        description="IANA timezone used to bucket active days (e.g. Europe/London)",
    ),
    device_id: UUID | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StatsSummary:
    return await service.summary(
        db,
        current_user.id,
        start=start,
        end=end,
        tz=tz,
        device_id=device_id,
    )


@router.get(
    "/applications",
    response_model=list[ApplicationStat],
    summary="Time per application in a window",
)
async def applications(
    start: datetime | None = Query(
        default=None,
        description="Window start (ISO-8601). Defaults to 24h before end.",
    ),
    end: datetime | None = Query(
        default=None,
        description="Window end (ISO-8601). Defaults to now.",
    ),
    device_id: UUID | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=service.MAX_APPLICATIONS),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ApplicationStat]:
    return await service.applications(
        db,
        current_user.id,
        start=start,
        end=end,
        device_id=device_id,
        limit=limit,
    )
