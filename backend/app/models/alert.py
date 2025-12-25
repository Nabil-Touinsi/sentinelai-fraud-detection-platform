from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

"""
Model Alert.

Rôle (fonctionnel) :
- Représente une alerte de fraude générée (ou gérée) à partir d’une transaction scorée.
- Contient un snapshot du score au moment de la création/mise à jour (score_snapshot).
- Porte un statut opérationnel (traitement) + une raison éventuelle (reason).

Relations :
- Alert -> Transaction (N alertes possibles pour 1 transaction selon la stratégie, ici relation via FK).
- Alert -> RiskScore (1 alerte associée à 1 risk_score ; unique=True sur risk_score_id).
- Alert -> AlertEvent (historique des actions / audit trail).

Index :
- Optimise les écrans “liste” et les filtres courants (par date + status, par date + score).
"""


class Alert(Base):
    __tablename__ = "alerts"

    # Identifiant technique (UUID)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Transaction associée (cascade delete)
    transaction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("transactions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Score associé (1 alerte <-> 1 risk_score)
    risk_score_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("risk_scores.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Snapshot du score au moment de l’alerte (utile si le score est recalculé plus tard)
    score_snapshot: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    # Statut opérationnel (workflow : ex open / A_TRAITER / RESOLU / etc.)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open", index=True)

    # Justification / commentaire libre (optionnel)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Horodatages
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    # Relations ORM (chargement joint pour les écrans de consultation)
    transaction = relationship("Transaction", back_populates="alerts", lazy="joined")
    risk_score = relationship("RiskScore", lazy="joined")
    events = relationship("AlertEvent", back_populates="alert")

    # Index composites pour accélérer les listes / dashboards (date + status / date + score)
    __table_args__ = (
        Index("ix_alerts_date_status", "created_at", "status"),
        Index("ix_alerts_date_score", "created_at", "score_snapshot"),
    )
