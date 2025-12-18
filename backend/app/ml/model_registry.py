from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional

import joblib

BASE_DIR = Path(__file__).resolve().parents[2]  # backend/
MODELS_DIR = BASE_DIR / "models"


@dataclass(frozen=True)
class LoadedModel:
    kind: str                 # "xgboost" | "iforest"
    model_version: str        # ex: "xgboost_v1_20251218-1410"
    model: Any
    spec: Dict[str, Any]
    meta: Dict[str, Any]


def _latest_file(prefix: str) -> Optional[Path]:
    if not MODELS_DIR.exists():
        return None
    files = sorted(MODELS_DIR.glob(f"{prefix}_*.joblib"), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


@lru_cache(maxsize=1)
def load_latest() -> Optional[LoadedModel]:
    """
    Charge le modèle le plus récent.
    Priorité: XGBoost puis fallback IsolationForest.
    """
    xgb_path = _latest_file("xgboost")
    iforest_path = _latest_file("iforest")

    chosen = xgb_path or iforest_path
    if not chosen:
        return None

    bundle = joblib.load(chosen)  # dict: {model, spec, meta}
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
