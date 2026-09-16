"""added session read indexes

Revision ID: c7a2e5f1d8b4
Revises: b4d1f8a2c9e3
Create Date: 2026-09-16 12:05:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'c7a2e5f1d8b4'
down_revision: Union[str, None] = 'b4d1f8a2c9e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        'ix_sessions_user_start_time',
        'sessions',
        ['user_id', 'start_time'],
        unique=False,
    )
    op.create_index(
        'ix_sessions_user_application_start_time',
        'sessions',
        ['user_id', 'application', 'start_time'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        'ix_sessions_user_application_start_time',
        table_name='sessions',
    )
    op.drop_index(
        'ix_sessions_user_start_time',
        table_name='sessions',
    )
