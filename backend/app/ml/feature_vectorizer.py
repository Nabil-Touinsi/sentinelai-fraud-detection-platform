from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple


@dataclass(frozen=True)
class FeatureSpec:
    categories: Tuple[str, ...]
    channels: Tuple[str, ...]
    zones: Tuple[str, ...]


def _one_hot(value: str, vocab: Tuple[str, ...]) -> List[float]:
    value = (value or "").lower()
    out = [0.0] * (len(vocab) + 1)  # +1 pour "other"
    if value in vocab:
        out[vocab.index(value)] = 1.0
    else:
        out[-1] = 1.0
    return out


def vectorize(features: Dict[str, Any], spec: FeatureSpec) -> List[float]:
    """
    IMPORTANT: Cette fonction est utilisée par:
      - les scripts d'entraînement
      - l'inférence runtime
    => garantit train == inference
    """
    hour = float(features.get("hour") or 0)
    amount = float(features.get("amount") or 0.0)
    is_online = 1.0 if bool(features.get("is_online")) else 0.0

    merchant_tx_count_24h = float(features.get("merchant_tx_count_24h") or 0.0)
    avg_amount_category_7d = features.get("avg_amount_category_7d")
    avg_amount_category_7d = float(avg_amount_category_7d) if avg_amount_category_7d is not None else 0.0

    category = (features.get("category") or "").lower()
    channel = (features.get("channel") or "").lower()
    zone = (features.get("arrondissement") or "").lower()

    x: List[float] = []
    # num
    x += [hour, amount, is_online, merchant_tx_count_24h, avg_amount_category_7d]
    # one-hot
    x += _one_hot(category, spec.categories)
    x += _one_hot(channel, spec.channels)
    x += _one_hot(zone, spec.zones)
    return x
