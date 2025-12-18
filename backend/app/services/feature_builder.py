from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.transaction import Transaction


class FeatureBuilder:
    """
    Construit un dictionnaire de features "simples mais crédibles"
    à partir d'une transaction + un peu de contexte DB.
    """

    async def build(self, db: AsyncSession, tx: Transaction) -> Dict[str, Any]:
        hour = tx.occurred_at.hour

        # Fenêtre glissante 24h sur "même commerçant" (proxy de fréquence)
        since_24h = tx.occurred_at - timedelta(hours=24)

        freq_stmt = (
            select(func.count(Transaction.id))
            .where(Transaction.merchant_name == tx.merchant_name)
            .where(Transaction.occurred_at >= since_24h)
        )
        merchant_tx_count_24h = (await db.execute(freq_stmt)).scalar_one()

        # Montant moyen 7 jours (proxy de "montant habituel" par catégorie)
        since_7d = tx.occurred_at - timedelta(days=7)

        avg_stmt = (
            select(func.avg(Transaction.amount))
            .where(Transaction.merchant_category == tx.merchant_category)
            .where(Transaction.occurred_at >= since_7d)
        )
        avg_amount_7d = (await db.execute(avg_stmt)).scalar()
        avg_amount_7d = float(avg_amount_7d) if avg_amount_7d is not None else None

        features: Dict[str, Any] = {
            "hour": hour,
            "amount": float(tx.amount),
            "currency": tx.currency,
            "category": tx.merchant_category,
            "merchant_name": tx.merchant_name,
            "arrondissement": tx.arrondissement,
            "channel": tx.channel,
            "is_online": bool(tx.is_online),
            "merchant_tx_count_24h": int(merchant_tx_count_24h),
            "avg_amount_category_7d": avg_amount_7d,
        }
        return features
