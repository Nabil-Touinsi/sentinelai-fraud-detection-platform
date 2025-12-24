"""add actor and request_id to alert_events

Revision ID: 3b1c7a9e2d11
Revises: 08fba70deb76
Create Date: 2025-12-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "3b1c7a9e2d11"
down_revision: Union[str, Sequence[str], None] = "08fba70deb76"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ✅ add columns
    op.add_column("alert_events", sa.Column("actor", sa.String(length=120), nullable=True))
    op.add_column("alert_events", sa.Column("request_id", sa.String(length=64), nullable=True))

    # ✅ add index for request_id (useful for traceability)
    op.create_index("ix_alert_events_request_id", "alert_events", ["request_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_alert_events_request_id", table_name="alert_events")
    op.drop_column("alert_events", "request_id")
    op.drop_column("alert_events", "actor")
