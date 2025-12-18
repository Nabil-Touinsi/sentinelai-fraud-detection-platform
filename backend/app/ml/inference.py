from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from app.ml.feature_vectorizer import FeatureSpec, vectorize
from app.ml.model_registry import load_latest


@dataclass(frozen=True)
class InferenceResult:
    score: int
    model_version: str
    kind: str


def _spec_from_dict(d: Dict[str, Any]) -> FeatureSpec:
    return FeatureSpec(
        categories=tuple(d["categories"]),
        channels=tuple(d["channels"]),
        zones=tuple(d["zones"]),
    )


def infer_score(features: Dict[str, Any]) -> Optional[InferenceResult]:
    """
    Retourne un score 0..100 basé sur le modèle le plus récent.
    Si aucun modèle => None.
    """
    loaded = load_latest()
    if not loaded:
        return None

    spec = _spec_from_dict(loaded.spec)
    x = vectorize(features, spec)
    X = [x]

    if loaded.kind == "xgboost":
        # proba fraude -> score
        proba = float(loaded.model.predict_proba(X)[0][1])
        score = int(round(max(0.0, min(1.0, proba)) * 100))
        return InferenceResult(score=score, model_version=loaded.model_version, kind="xgboost")

    if loaded.kind == "iforest":
        # isolation forest: decision_function haut = normal
        q05 = float(loaded.meta.get("q05", -0.2))
        q95 = float(loaded.meta.get("q95", 0.2))
        d = float(loaded.model.decision_function(X)[0])
        anomaly = -d
        denom = (q95 - q05) if (q95 - q05) != 0 else 1.0
        norm = (anomaly - q05) / denom
        norm = max(0.0, min(1.0, norm))
        score = int(round(norm * 100))
        return InferenceResult(score=score, model_version=loaded.model_version, kind="iforest")

    return None
