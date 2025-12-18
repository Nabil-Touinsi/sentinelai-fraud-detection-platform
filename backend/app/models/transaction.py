from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR")

    merchant_name: Mapped[str] = mapped_column(String(255), nullable=False)
    merchant_category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    arrondissement: Mapped[str | None] = mapped_column(String(50), nullable=True)
    channel: Mapped[str] = mapped_column(String(30), nullable=False, default="card")
    is_online: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relations (1 RiskScore max, 0..n Alerts)
    risk_score = relationship("RiskScore", back_populates="transaction", uselist=False)
    alerts = relationship("Alert", back_populates="transaction")

    __table_args__ = (
        Index("ix_transactions_date_amount", "occurred_at", "amount"),
    )
