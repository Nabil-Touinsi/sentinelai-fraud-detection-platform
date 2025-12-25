"""${message}

Rôle (fonctionnel) :
- Modèle utilisé par Alembic pour générer un nouveau fichier de migration.
- Les champs Revision ID / Revises / Create Date sont remplis automatiquement.
- Les fonctions upgrade()/downgrade() contiennent les changements de schéma.

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# Identifiants Alembic
revision: str = ${repr(up_revision)}
down_revision: Union[str, Sequence[str], None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    """Application des changements de schéma."""
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    """Retour arrière des changements de schéma."""
    ${downgrades if downgrades else "pass"}
