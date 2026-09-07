import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.choices import EventType, Source


class HeartbeatCreate(BaseModel):
    local_id: uuid.UUID = Field(description="Device event UUID (dedupe key)")
    state_id: uuid.UUID = Field(description="Device state id for this event")
    source: Source = Field(default=Source.OS, description="Observation source")
    application: str = Field(description="Normalized application identifier")
    event_type: EventType = Field(
        default=EventType.HEARTBEAT, description="Event type"
    )
    timestamp: datetime = Field(description="Device time the heartbeat was recorded")
    duration_seconds: float | None = Field(
        default=None, description="Seconds covered by this heartbeat"
    )
    process_id: int | None = Field(default=None)
    window_title: str | None = Field(default=None)


class HeartbeatIngestResult(BaseModel):
    """Result returned after a batch of heartbeats is ingested."""

    received: int = Field(description="Number of new heartbeats stored")
    skipped: int = Field(description="Duplicates (same local_id) already present")
