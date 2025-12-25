from __future__ import annotations

import time
from dataclasses import dataclass
from threading import Lock
from typing import Dict, Tuple

from fastapi import Request

from app.core.errors import AppHTTPException
from app.core.settings import settings

"""
Core Rate Limit.

Rôle (fonctionnel) :
- Protège l’API contre les rafales de requêtes (anti-abus) avec un rate limit simple.
- Implémentation “in-memory” par IP + route (method + path), fenêtre fixe de 60 secondes (RPM).
- Conçu pour démo / local : en production, une implémentation distribuée (ex : Redis) est recommandée.

Activation via settings :
- RATE_LIMIT_ENABLED : active/désactive le rate limiting.
- RATE_LIMIT_RPM : limite de requêtes par minute (par IP + route).
"""


@dataclass
class _Bucket:
    """État minimal d’un compteur sur une fenêtre fixe."""
    window_start: float
    count: int


class InMemoryRateLimiter:
    """
    Rate limiter en mémoire (best-effort).

    Principe :
    - Stocke un compteur par clé (IP, "METHOD /path") sur une fenêtre de 60s.
    - Réinitialise le compteur à chaque nouvelle fenêtre.
    - Déclenche AppHTTPException(429) si la limite est dépassée.
    """

    def __init__(self) -> None:
        # Lock pour garantir la cohérence en cas de concurrence (threads / workers)
        self._lock = Lock()
        self._buckets: Dict[Tuple[str, str], _Bucket] = {}

    def _client_ip(self, request: Request) -> str:
        """Récupère l’IP client (à adapter si reverse proxy : X-Forwarded-For)."""
        return request.client.host if request.client else "unknown"

    def check(self, request: Request) -> None:
        """Vérifie la limite pour (IP + route). Lève 429 si dépassement."""
        if not getattr(settings, "RATE_LIMIT_ENABLED", False):
            return

        limit = int(getattr(settings, "RATE_LIMIT_RPM", 120) or 120)
        if limit <= 0:
            return

        ip = self._client_ip(request)

        # Clé par route : (IP, "METHOD /path")
        key = (ip, f"{request.method} {request.url.path}")

        now = time.time()
        window = 60.0

        with self._lock:
            bucket = self._buckets.get(key)

            # Nouvelle fenêtre : on réinitialise
            if bucket is None or (now - bucket.window_start) >= window:
                self._buckets[key] = _Bucket(window_start=now, count=1)
                return

            bucket.count += 1

            # Dépassement : 429 (Too Many Requests)
            if bucket.count > limit:
                raise AppHTTPException(
                    429,
                    "RATE_LIMITED",
                    f"Trop de requêtes (limite: {limit}/min).",
                    details={"limit_rpm": limit},
                )


# Instance globale importable (utilisée dans le middleware / endpoints)
rate_limiter = InMemoryRateLimiter()
