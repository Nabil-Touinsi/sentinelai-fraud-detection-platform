from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

"""
Model Transaction.

Rôle (fonctionnel) :
- Représente une transaction financière “brute” (événement d’entrée) à scorer.
- Sert de pivot métier : le scoring (RiskScore) et la détection (Alert) se rattachent à la transaction.

Champs principaux :
- occurred_at : date/heure de l’événement (utile pour analytics, séries temporelles).
- amount/currency : montant (Numeric) et devise.
- merchant_* : informations commerçant (nom + catégorie).
- arrondissement / channel / is_online : signaux contextuels pour UI + features ML.
- description : texte libre optionnel.

Relations :
- Transaction -> RiskScore : 1..0 (au plus un score par transaction).
- Transaction -> Alert : 1..N (historique / stratégie de création d’alertes).

Index :
- Optimise requêtes fréquentes : tri/filtres par date, et par montant.
"""


class Transaction(Base):
    __tablename__ = "transactions"

    # Identifiant technique (UUID)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Horodatages : événement (occurred) vs insertion (created)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    # Montant et devise
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR")

    # Données commerçant
    merchant_name: Mapped[str] = mapped_column(String(255), nullable=False)
    merchant_category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    # Contexte (zone + canal)
    arrondissement: Mapped[str | None] = mapped_column(String(50), nullable=True)
    channel: Mapped[str] = mapped_column(String(30), nullable=False, default="card")
    is_online: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Texte libre optionnel
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relations (1 RiskScore max, 0..n Alerts)
    risk_score = relationship("RiskScore", back_populates="transaction", uselist=False)
    alerts = relationship("Alert", back_populates="transaction")

    # Index composite utile pour analytics (date + amount)
    __table_args__ = (
        Index("ix_transactions_date_amount", "occurred_at", "amount"),
    )
