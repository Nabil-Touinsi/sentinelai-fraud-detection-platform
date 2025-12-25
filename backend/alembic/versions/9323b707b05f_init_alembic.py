"""Initialisation d’Alembic.

Rôle (fonctionnel) :
- Migration de base (point de départ) pour l’historique Alembic.
- Elle ne modifie pas le schéma : elle sert uniquement d’ancrage pour les migrations suivantes.

Revision ID: 9323b707b05f
Revises:
Create Date: 2025-12-14 19:42:05.603951
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# Identifiants Alembic
revision: str = "9323b707b05f"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Application des changements de schéma."""
    pass


def downgrade() -> None:
    """Retour arrière des changements de schéma."""
    pass
