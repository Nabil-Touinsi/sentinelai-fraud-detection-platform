from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

"""
Model RiskScore.

Rôle (fonctionnel) :
- Stocke le résultat de scoring pour une transaction (score 0..100).
- Conserve la version du modèle ayant produit le score (model_version).
- Optionnellement, conserve le snapshot des features utilisées (features, JSONB) pour audit/debug.

Contraintes :
- 1 transaction -> 1 risk_score (unique=True sur transaction_id).
- Suppression en cascade : si la transaction est supprimée, son score l’est aussi.

Index :
- Optimise les listes et dashboards : (created_at, score) pour filtres/tri par date et score.
"""


class RiskScore(Base):
    __tablename__ = "risk_scores"

    # Identifiant technique (UUID)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Transaction associée (1:1 via contrainte unique)
    transaction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("transactions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Score de risque normalisé (0..100)
    score: Mapped[int] = mapped_column(Integer, nullable=False, index=True)  # 0..100

    # Version du modèle (ex: v1 / xgboost_v1_... / iforest_v1_...)
    model_version: Mapped[str] = mapped_column(String(50), nullable=False, default="v1")

    # Snapshot des features utilisées pour le scoring (audit / debug) — optionnel
    features: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Horodatage du scoring
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow, index=True)

    # Relation ORM : accès direct à la transaction (chargement joint)
    transaction = relationship("Transaction", back_populates="risk_score", lazy="joined")

    # Index composite pour accélérer les requêtes (date + score)
    __table_args__ = (Index("ix_risk_scores_date_score", "created_at", "score"),)
