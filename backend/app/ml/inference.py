from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from app.ml.feature_vectorizer import FeatureSpec, vectorize
from app.ml.model_registry import load_latest

"""
ML Inference.

Rôle (fonctionnel) :
- Charge le modèle “le plus récent” via le registry (load_latest).
- Transforme les features brutes en vecteur (vectorize) avec le FeatureSpec du modèle.
- Exécute l’inférence et normalise le résultat en score 0..100.

Comportement :
- Si aucun modèle n’est disponible : retourne None (mode dégradé).
- Supporte plusieurs “kinds” de modèles :
  - xgboost : utilise predict_proba -> probabilité de fraude -> score 0..100
  - iforest : utilise decision_function -> convertit en anomalie -> normalisation via quantiles

Notes :
- L’ordre et l’encodage des features doivent rester identiques entre train et inference.
- La normalisation iforest dépend de métadonnées (q05/q95) fournies par le registry.
"""


@dataclass(frozen=True)
class InferenceResult:
    """Résultat d’inférence standardisé."""
    score: int
    model_version: str
    kind: str


def _spec_from_dict(d: Dict[str, Any]) -> FeatureSpec:
    """Convertit un dict (registry) en FeatureSpec typé."""
    return FeatureSpec(
        categories=tuple(d["categories"]),
        channels=tuple(d["channels"]),
        zones=tuple(d["zones"]),
    )


def infer_score(features: Dict[str, Any]) -> Optional[InferenceResult]:
    """
    Retourne un score 0..100 basé sur le modèle le plus récent.

    - Si aucun modèle disponible : None
    - Sinon : score normalisé + version du modèle + type (kind)
    """
    loaded = load_latest()
    if not loaded:
        return None

    # Vectorisation canonique (train == inference)
    spec = _spec_from_dict(loaded.spec)
    x = vectorize(features, spec)
    X = [x]

    if loaded.kind == "xgboost":
        # Proba fraude -> score 0..100
        proba = float(loaded.model.predict_proba(X)[0][1])
        score = int(round(max(0.0, min(1.0, proba)) * 100))
        return InferenceResult(score=score, model_version=loaded.model_version, kind="xgboost")

    if loaded.kind == "iforest":
        # Isolation Forest :
        # - decision_function élevé = normal
        # - on inverse pour obtenir une “anomalie”, puis normalise via q05/q95
        q05 = float(loaded.meta.get("q05", -0.2))
        q95 = float(loaded.meta.get("q95", 0.2))
        d = float(loaded.model.decision_function(X)[0])
        anomaly = -d
        denom = (q95 - q05) if (q95 - q05) != 0 else 1.0
        norm = (anomaly - q05) / denom
        norm = max(0.0, min(1.0, norm))
        score = int(round(norm * 100))
        return InferenceResult(score=score, model_version=loaded.model_version, kind="iforest")

    # Kind inconnu / non supporté
    return None
