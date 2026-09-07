import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.choices import EventType, Source
from app.db.base import Base


class Heartbeat(Base):
    __tablename__ = "heartbeats"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    local_id: Mapped[uuid.UUID] = mapped_column(Uuid, unique=True)
    state_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    source: Mapped[str] = mapped_column(String(16), default=Source.OS.value)
    application: Mapped[str] = mapped_column(String(255), index=True)
    event_type: Mapped[str] = mapped_column(
        String(24), default=EventType.HEARTBEAT.value, index=True
    )
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    process_id: Mapped[int | None] = mapped_column(Integer)
    window_title: Mapped[str | None] = mapped_column(Text)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"Heartbeat(id={self.id!r}, application={self.application!r}, "
            f"timestamp={self.timestamp!r})"
        )
