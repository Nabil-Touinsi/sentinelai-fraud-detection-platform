from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional

import joblib

"""
ML Model Registry.

Rôle (fonctionnel) :
- Localise et charge les artefacts modèles depuis le dossier backend/models.
- Sélectionne automatiquement le modèle “le plus récent” (par date de modification).
- Retourne un bundle typé (LoadedModel) contenant :
  - kind (type de modèle)
  - model_version (version lisible)
  - model (objet ML sérialisé)
  - spec (vocabulaires / paramètres de vectorisation)
  - meta (métadonnées : quantiles, kind, etc.)

Conventions :
- Les fichiers sont attendus sous la forme : <prefix>_*.joblib
  Ex : xgboost_v1_20251218-1410.joblib, iforest_v1_....
- La sélection du “latest” est basée sur st_mtime (date de dernière modification du fichier).

Notes :
- load_latest() est caché (lru_cache) pour éviter de recharger le modèle à chaque requête.
- En production, on peut remplacer ce registry fichier par un registry externe (S3, MLflow, etc.).
"""

BASE_DIR = Path(__file__).resolve().parents[2]  # backend/
MODELS_DIR = BASE_DIR / "models"


@dataclass(frozen=True)
class LoadedModel:
    """Bundle modèle chargé (objet + spec + meta) prêt pour l’inférence."""
    kind: str                 # "xgboost" | "iforest"
    model_version: str        # ex: "xgboost_v1_20251218-1410"
    model: Any
    spec: Dict[str, Any]
    meta: Dict[str, Any]


def _latest_file(prefix: str) -> Optional[Path]:
    """Retourne le fichier .joblib le plus récent pour un prefix donné (ou None)."""
    if not MODELS_DIR.exists():
        return None
    files = sorted(MODELS_DIR.glob(f"{prefix}_*.joblib"), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


@lru_cache(maxsize=1)
def load_latest() -> Optional[LoadedModel]:
    """
    Charge le modèle le plus récent depuis backend/models.

    Stratégie :
- Priorité : XGBoost si présent
- Fallback : IsolationForest si XGBoost absent
- Sinon : None (mode dégradé)

    Retour :
- LoadedModel contenant (kind, version, model, spec, meta)
    """
    xgb_path = _latest_file("xgboost")
    iforest_path = _latest_file("iforest")

    chosen = xgb_path or iforest_path
    if not chosen:
        return None

    # Bundle attendu : dict { "model": ..., "spec": ..., "meta": ... }
    bundle = joblib.load(chosen)
    meta = bundle.get("meta", {})
    kind = meta.get("kind", "unknown")
    version = meta.get("model_version", chosen.stem)

    return LoadedModel(
        kind=kind,
        model_version=version,
        model=bundle["model"],
        spec=bundle["spec"],
        meta=meta,
    )
