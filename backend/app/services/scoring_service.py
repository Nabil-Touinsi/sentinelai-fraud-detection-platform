from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.risk_score import RiskScore
from app.models.transaction import Transaction
from app.services.feature_builder import FeatureBuilder


@dataclass(frozen=True)
class ScoringResult:
    score: int                 # 0..100
    risk_level: str            # LOW / MEDIUM / HIGH
    factors: List[str]         # explications courtes
    features: Dict[str, Any]   # features calculées
    model_version: str         # ex: "rules_v1" / "xgboost_v1" ...


class ScoringService:
    """
    Scoring déterministe (règles) + option ML.
    Sauvegarde en DB dans risk_scores (1 ligne par transaction).
    """

    def __init__(
        self,
        feature_builder: FeatureBuilder | None = None,
        *,
        model_version: str = "rules_v1",
        high_risk_categories: Tuple[str, ...] = ("ecommerce", "electronics", "hotel"),
        high_risk_zones: Tuple[str, ...] = ("Saint-Denis", "Aubervilliers", "Montreuil"),
    ) -> None:
        self.feature_builder = feature_builder or FeatureBuilder()
        self.model_version = model_version
        self.high_risk_categories = tuple(c.lower() for c in high_risk_categories)
        self.high_risk_zones = tuple(z.lower() for z in high_risk_zones)

    def _risk_level(self, score: int) -> str:
        if score >= 70:
            return "HIGH"
        if score >= 40:
            return "MEDIUM"
        return "LOW"

    def _apply_rules(self, f: Dict[str, Any]) -> Tuple[int, List[str]]:
        score = 10
        factors: List[str] = []

        amount = float(f["amount"])
        hour = int(f["hour"])
        category = (f.get("category") or "").lower()
        zone = (f.get("arrondissement") or "").lower()
        is_online = bool(f.get("is_online"))
        merchant_tx_count_24h = int(f.get("merchant_tx_count_24h") or 0)
        avg_amount_7d = f.get("avg_amount_category_7d")

        # 1) Montant (paliers simples)
        if amount >= 200:
            score += 35
            factors.append("Montant très élevé (>= 200€)")
        elif amount >= 120:
            score += 20
            factors.append("Montant élevé (>= 120€)")
        elif amount >= 60:
            score += 10
            factors.append("Montant au-dessus de la moyenne (>= 60€)")

        # 2) Heures atypiques
        if hour <= 5:
            score += 20
            factors.append("Horaire atypique (nuit)")
        elif hour <= 7:
            score += 10
            factors.append("Horaire tôt le matin")

        # 3) En ligne
        if is_online:
            score += 10
            factors.append("Transaction en ligne")

        # 4) Catégories “risque”
        if category in self.high_risk_categories:
            score += 15
            factors.append(f"Catégorie à risque ({category})")

        # 5) Zone “risque” (proxy géographique)
        if zone and zone in self.high_risk_zones:
            score += 10
            factors.append("Zone sensible")

        # 6) Fréquence récente (même merchant sur 24h)
        if merchant_tx_count_24h >= 5:
            score += 15
            factors.append("Fréquence élevée (>= 5 transactions/24h chez ce commerçant)")
        elif merchant_tx_count_24h >= 3:
            score += 8
            factors.append("Fréquence modérée (>= 3 transactions/24h chez ce commerçant)")

        # 7) Montant vs moyenne catégorie (si dispo)
        if avg_amount_7d is not None and float(avg_amount_7d) > 0:
            if amount >= 2.0 * float(avg_amount_7d):
                score += 10
                factors.append("Montant très supérieur à la moyenne de la catégorie (7j)")

        # clamp 0..100
        score = max(0, min(100, score))

        # garde seulement 3–5 facteurs lisibles
        factors = factors[:5]
        return score, factors

    async def score_and_persist(self, db: AsyncSession, tx: Transaction) -> ScoringResult:
        features = await self.feature_builder.build(db, tx)

        # 1) Score règles (base)
        rules_score, rules_factors = self._apply_rules(features)

        # Valeurs par défaut (si ML KO)
        final_score = rules_score
        final_factors = rules_factors
        final_model_version = self.model_version  # rules_v1 par défaut

        # 2) ML (optionnel) -> on garde le score le PLUS ÉLEVÉ (max)
        try:
            from app.ml.inference import infer_score

            ml = infer_score(features)
            if ml is not None:
                # robustesse: score int 0..100
                ml_score = int(max(0, min(100, getattr(ml, "score", 0))))

                # IMPORTANT: ne pas écraser les règles
                final_score = max(rules_score, ml_score)

                # on ajoute l’info modèle, mais on garde les facteurs règles
                ml_kind = getattr(ml, "kind", "ml")
                final_factors = ([f"Modèle IA utilisé: {ml_kind}"] + rules_factors)[:5]

                # version modèle ML si dispo, sinon on garde rules_v1
                final_model_version = getattr(ml, "model_version", final_model_version)
        except Exception:
            # si un problème ML survient, on garde le scoring règles
            pass

        level = self._risk_level(final_score)

        payload = {
            "inputs": features,
            "factors": final_factors,
            "risk_level": level,
            "rules_score": rules_score,
            # utile debug (optionnel)
            "final_score": final_score,
        }

        # ✅ UPSERT : 1 score par transaction (transaction_id est unique)
        existing = (
            await db.execute(select(RiskScore).where(RiskScore.transaction_id == tx.id))
        ).scalars().first()

        now = datetime.utcnow()

        if existing:
            existing.score = final_score
            existing.model_version = final_model_version
            existing.features = payload
            existing.created_at = now
            rs = existing
        else:
            rs = RiskScore(
                transaction_id=tx.id,
                score=final_score,
                model_version=final_model_version,
                features=payload,
                created_at=now,
            )
            db.add(rs)

        await db.commit()
        await db.refresh(rs)

        # garde aussi self.model_version cohérent pour le retour
        self.model_version = final_model_version

        return ScoringResult(
            score=final_score,
            risk_level=level,
            factors=final_factors,
            features=features,
            model_version=final_model_version,
        )
