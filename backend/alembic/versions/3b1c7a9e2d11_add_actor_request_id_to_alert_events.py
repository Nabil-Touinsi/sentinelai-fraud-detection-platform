"""Ajout des champs actor et request_id à la table alert_events.

Rôle (fonctionnel) :
- actor : identifie l’auteur de l’action (ex. "system", "admin", "analyst:Jean", etc.)
- request_id : identifiant de requête pour recouper un event avec les logs/API
Ces champs servent à la traçabilité des actions sur les alertes (audit).

Revision ID: 3b1c7a9e2d11
Revises: 08fba70deb76
Create Date: 2025-12-22
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# Identifiants Alembic
revision: str = "3b1c7a9e2d11"
down_revision: Union[str, Sequence[str], None] = "08fba70deb76"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Application des changements de schéma."""
    op.add_column("alert_events", sa.Column("actor", sa.String(length=120), nullable=True))
    op.add_column("alert_events", sa.Column("request_id", sa.String(length=64), nullable=True))
    op.create_index("ix_alert_events_request_id", "alert_events", ["request_id"], unique=False)


def downgrade() -> None:
    """Retour arrière des changements de schéma."""
    op.drop_index("ix_alert_events_request_id", table_name="alert_events")
    op.drop_column("alert_events", "request_id")
    op.drop_column("alert_events", "actor")
