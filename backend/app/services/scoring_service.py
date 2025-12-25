from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.risk_score import RiskScore
from app.models.transaction import Transaction
from app.services.feature_builder import FeatureBuilder

"""
Scoring Service.

Rôle (fonctionnel) :
- Calcule un score de risque 0..100 pour une transaction.
- Combine :
  - un scoring déterministe par règles (base stable)
  - un scoring ML optionnel (si un modèle est disponible)
- Persiste le résultat dans la table risk_scores (1 ligne par transaction, UPSERT).

Principe de fusion règles + ML :
- Les règles servent de baseline “compréhensible” (factors lisibles).
- Si le ML est disponible, on garde un comportement conservateur :
  final_score = max(score_règles, score_ML)
  -> on évite que le ML “désamorce” un signal de risque détecté par les règles.

Sortie :
- ScoringResult : score + niveau (LOW/MEDIUM/HIGH) + facteurs + features + version modèle.
"""


@dataclass(frozen=True)
class ScoringResult:
    """Résultat de scoring retourné aux endpoints (et utile pour logs / UI)."""
    score: int                 # 0..100
    risk_level: str            # LOW / MEDIUM / HIGH
    factors: List[str]         # explications courtes
    features: Dict[str, Any]   # features calculées
    model_version: str         # ex: "rules_v1" / "xgboost_v1" ...


class ScoringService:
    """
    Service de scoring (règles + ML optionnel) avec persistance.

    Responsabilités :
    - Construire les features (FeatureBuilder)
    - Appliquer les règles (explicables)
    - Appeler le ML si dispo (best-effort)
    - Sauvegarder dans RiskScore (UPSERT transaction_id unique)
    """

    def __init__(
        self,
        feature_builder: FeatureBuilder | None = None,
        *,
        model_version: str = "rules_v1",
        high_risk_categories: Tuple[str, ...] = ("ecommerce", "electronics", "hotel"),
        high_risk_zones: Tuple[str, ...] = ("Saint-Denis", "Aubervilliers", "Montreuil"),
    ) -> None:
        # Builder injectable pour tests / variations
        self.feature_builder = feature_builder or FeatureBuilder()

        # Version de fallback (si ML indisponible)
        self.model_version = model_version

        # Config règles (normalisée en lower)
        self.high_risk_categories = tuple(c.lower() for c in high_risk_categories)
        self.high_risk_zones = tuple(z.lower() for z in high_risk_zones)

    def _risk_level(self, score: int) -> str:
        """Bucket simple pour l’UI (LOW / MEDIUM / HIGH)."""
        if score >= 70:
            return "HIGH"
        if score >= 40:
            return "MEDIUM"
        return "LOW"

    def _apply_rules(self, f: Dict[str, Any]) -> Tuple[int, List[str]]:
        """
        Applique un set de règles lisibles et renvoie :
        - score (0..100)
        - facteurs (liste courte d’explications)

        Objectif :
        - Avoir des résultats “crédibles” et interprétables, même sans ML.
        """
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

        # Clamp 0..100
        score = max(0, min(100, score))

        # Garde seulement 3–5 facteurs lisibles
        factors = factors[:5]
        return score, factors

    async def score_and_persist(self, db: AsyncSession, tx: Transaction) -> ScoringResult:
        """
        Orchestration complète :
        - build features
        - compute score (règles + ML optionnel)
        - persist (UPSERT) dans RiskScore
        - retourne ScoringResult (utilisé par /score et d’autres flows)
        """
        features = await self.feature_builder.build(db, tx)

        # 1) Score règles (baseline)
        rules_score, rules_factors = self._apply_rules(features)

        # Valeurs par défaut (si ML indisponible)
        final_score = rules_score
        final_factors = rules_factors
        final_model_version = self.model_version  # rules_v1 par défaut

        # 2) ML (optionnel) : best-effort
        # Stratégie conservatrice : on garde le score le plus élevé (max)
        try:
            from app.ml.inference import infer_score

            ml = infer_score(features)
            if ml is not None:
                # Robustesse : score int 0..100
                ml_score = int(max(0, min(100, getattr(ml, "score", 0))))

                # IMPORTANT : ne pas “désamorcer” les règles
                final_score = max(rules_score, ml_score)

                # On expose l’info modèle, mais on garde les facteurs règles (lisibles)
                ml_kind = getattr(ml, "kind", "ml")
                final_factors = ([f"Modèle IA utilisé: {ml_kind}"] + rules_factors)[:5]

                # Version modèle ML si dispo, sinon fallback sur version courante
                final_model_version = getattr(ml, "model_version", final_model_version)
        except Exception:
            # En cas de problème ML : scoring règles seulement
            pass

        level = self._risk_level(final_score)

        # Payload utile pour audit/debug (stocké dans RiskScore.features)
        payload = {
            "inputs": features,
            "factors": final_factors,
            "risk_level": level,
            "rules_score": rules_score,
            "final_score": final_score,
        }

        # UPSERT : 1 score par transaction (transaction_id est unique)
        existing = (await db.execute(select(RiskScore).where(RiskScore.transaction_id == tx.id))).scalars().first()

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

        self.model_version = final_model_version

        return ScoringResult(
            score=final_score,
            risk_level=level,
            factors=final_factors,
            features=features,
            model_version=final_model_version,
        )
