from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.users import User
from app.schemas.session import SessionOut, SessionPage
from app.services import analytics as service

router = APIRouter(tags=["sessions"])


@router.get(
    "",
    response_model=SessionPage,
    summary="List the current user's sessions",
)
async def list_sessions(
    start: datetime | None = Query(
        default=None,
        description="Window start (ISO-8601). Defaults to 24h before end.",
    ),
    end: datetime | None = Query(
        default=None,
        description="Window end (ISO-8601). Defaults to now.",
    ),
    application: str | None = Query(default=None),
    device_id: UUID | None = Query(default=None),
    source: str | None = Query(default=None),
    cursor: str | None = Query(
        default=None, description="Opaque cursor taken from a previous next_cursor"
    ),
    limit: int = Query(
        default=service.PAGE_SIZE, ge=1, le=service.MAX_PAGE_SIZE
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SessionPage:
    return await service.list_sessions(
        db,
        current_user.id,
        start=start,
        end=end,
        application=application,
        device_id=device_id,
        source=source,
        cursor=cursor,
        limit=limit,
    )


@router.get(
    "/{session_id}",
    response_model=SessionOut,
    summary="Fetch one of the current user's sessions",
)
async def get_session(
    session_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SessionOut:
    return await service.get_session(db, current_user.id, session_id)
