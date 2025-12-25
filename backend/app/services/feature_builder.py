from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.transaction import Transaction

"""
Feature Builder.

Rôle (fonctionnel) :
- Construit un dictionnaire de features “simples mais crédibles” pour le scoring.
- Combine :
  - signaux directs de la transaction (montant, canal, arrondissement, heure…)
  - signaux contextuels calculés en DB sur des fenêtres glissantes (24h / 7 jours)

Objectif :
- Fournir un format stable consommé par :
  - le vectorizer (app.ml.feature_vectorizer)
  - l’inférence (app.ml.inference)
  - la persistance dans RiskScore.features (audit/debug)

Notes :
- Les features restent volontairement “légères” : assez réalistes pour une démo,
  sans complexité data science (pas de jointures lourdes / pas de state externe).
"""


class FeatureBuilder:
    """
    Construit un dictionnaire de features à partir d'une transaction + contexte DB.

    Features calculées :
    - hour : heure de la transaction
    - merchant_tx_count_24h : fréquence 24h sur le même merchant (proxy “burst / répétition”)
    - avg_amount_category_7d : moyenne 7j sur la même catégorie (proxy “montant habituel”)
    """

    async def build(self, db: AsyncSession, tx: Transaction) -> Dict[str, Any]:
        hour = tx.occurred_at.hour

        # Fenêtre glissante 24h : fréquence pour le même marchand (proxy de répétition)
        since_24h = tx.occurred_at - timedelta(hours=24)

        freq_stmt = (
            select(func.count(Transaction.id))
            .where(Transaction.merchant_name == tx.merchant_name)
            .where(Transaction.occurred_at >= since_24h)
        )
        merchant_tx_count_24h = (await db.execute(freq_stmt)).scalar_one()

        # Fenêtre glissante 7j : montant moyen par catégorie (proxy de “montant habituel”)
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
