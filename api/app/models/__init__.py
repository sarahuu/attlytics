"""SQLAlchemy ORM models.

Import every model here so Alembic autogenerate (alembic/env.py) can see the
full metadata when generating migrations.
"""

from app.models.heartbeat import Heartbeat

__all__ = ["Heartbeat"]
