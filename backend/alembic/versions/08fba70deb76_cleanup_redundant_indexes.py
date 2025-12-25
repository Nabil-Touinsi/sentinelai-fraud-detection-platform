"""Nettoyage d’index redondants.

Rôle (fonctionnel) :
- Cette migration ne change pas le comportement applicatif.
- Elle supprime des index qui faisaient doublon avec d’autres index déjà présents.
- Objectif : garder un schéma plus propre et éviter de dégrader les performances en écriture.

Revision ID: 08fba70deb76
Revises: 1fe285a86c40
Create Date: 2025-12-14 20:19:40.368661
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# Identifiants Alembic
revision: str = "08fba70deb76"
down_revision: Union[str, Sequence[str], None] = "1fe285a86c40"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Application des changements de schéma."""
    op.drop_index(op.f("ix_alert_events_date"), table_name="alert_events")
    op.drop_index(op.f("ix_alerts_created_at"), table_name="alerts")
    op.drop_index(op.f("ix_risk_scores_created_at"), table_name="risk_scores")
    op.drop_index(op.f("ix_transactions_occurred_at"), table_name="transactions")


def downgrade() -> None:
    """Retour arrière des changements de schéma."""
    op.create_index(op.f("ix_transactions_occurred_at"), "transactions", ["occurred_at"], unique=False)
    op.create_index(op.f("ix_risk_scores_created_at"), "risk_scores", ["created_at"], unique=False)
    op.create_index(op.f("ix_alerts_created_at"), "alerts", ["created_at"], unique=False)
    op.create_index(op.f("ix_alert_events_date"), "alert_events", ["created_at"], unique=False)
