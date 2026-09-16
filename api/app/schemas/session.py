import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class SessionOut(BaseModel):

    id: uuid.UUID
    device_id: uuid.UUID
    state_id: uuid.UUID
    source: str
    application: str
    start_time: datetime
    end_time: datetime | None = None
    duration_seconds: float | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SessionPage(BaseModel):
    items: list[SessionOut]
    next_cursor: str | None = Field(
        default=None,
        description="Opaque cursor; pass back as ?cursor= to fetch the next page",
    )


class StatsSummary(BaseModel):
    """Totals over a time window."""

    total_seconds: float = Field(description="Summed session durations")
    session_count: int
    active_days: int = Field(description="Distinct local days with activity")
    average_seconds_per_active_day: float
    longest_session_seconds: float
    first_activity: datetime | None = None
    last_activity: datetime | None = None


class ApplicationStat(BaseModel):
    """Time attributed to one application within a window."""

    application: str
    total_seconds: float
    session_count: int
    share_percent: float = Field(
        description="Share of all tracked time in the window, not just this page"
    )
