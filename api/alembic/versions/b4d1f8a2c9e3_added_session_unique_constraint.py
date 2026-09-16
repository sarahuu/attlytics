"""added session unique constraint

Revision ID: b4d1f8a2c9e3
Revises: 9f962d09b72d
Create Date: 2026-09-16 11:20:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'b4d1f8a2c9e3'
down_revision: Union[str, None] = '9f962d09b72d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


MERGE_DUPLICATES = """
WITH ranked AS (
    SELECT
        id,
        MIN(start_time) OVER w AS start_time,
        MAX(end_time) OVER w AS end_time,
        ROW_NUMBER() OVER (
            PARTITION BY user_id, device_id, state_id
            ORDER BY created_at, id
        ) AS rn
    FROM sessions
    WINDOW w AS (PARTITION BY user_id, device_id, state_id)
)
UPDATE sessions AS s
SET start_time = r.start_time,
    end_time = r.end_time,
    duration_seconds = CASE
        WHEN r.end_time IS NOT NULL
        THEN EXTRACT(EPOCH FROM (r.end_time - r.start_time))::double precision
        ELSE s.duration_seconds
    END
FROM ranked AS r
WHERE s.id = r.id
  AND r.rn = 1
"""


DELETE_DUPLICATES = """
DELETE FROM sessions AS s
USING (
    SELECT
        id,
        ROW_NUMBER() OVER (
            PARTITION BY user_id, device_id, state_id
            ORDER BY created_at, id
        ) AS rn
    FROM sessions
) AS ranked
WHERE s.id = ranked.id
  AND ranked.rn > 1
"""


def upgrade() -> None:
    op.execute(MERGE_DUPLICATES)
    op.execute(DELETE_DUPLICATES)
    op.create_unique_constraint(
        'uq_sessions_user_device_state',
        'sessions',
        ['user_id', 'device_id', 'state_id'],
    )


def downgrade() -> None:
    op.drop_constraint(
        'uq_sessions_user_device_state',
        'sessions',
        type_='unique',
    )
