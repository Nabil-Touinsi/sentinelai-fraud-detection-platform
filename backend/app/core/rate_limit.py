from __future__ import annotations

import time
from dataclasses import dataclass
from threading import Lock
from typing import Dict, Tuple

from fastapi import Request

from app.core.errors import AppHTTPException
from app.core.settings import settings


@dataclass
class _Bucket:
    window_start: float
    count: int


class InMemoryRateLimiter:
    """
    Rate limit simple en mémoire, par IP + route.
    Fenêtre fixe 60s (RPM).
    Suffisant pour démo / local. (En prod réel => Redis)
    """

    def __init__(self) -> None:
        self._lock = Lock()
        self._buckets: Dict[Tuple[str, str], _Bucket] = {}

    def _client_ip(self, request: Request) -> str:
        # Si tu es derrière proxy, adapte avec X-Forwarded-For.
        return request.client.host if request.client else "unknown"

    def check(self, request: Request) -> None:
        if not getattr(settings, "RATE_LIMIT_ENABLED", False):
            return

        limit = int(getattr(settings, "RATE_LIMIT_RPM", 120) or 120)
        if limit <= 0:
            return

        ip = self._client_ip(request)
        # clé par route (method + path)
        key = (ip, f"{request.method} {request.url.path}")

        now = time.time()
        window = 60.0

        with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None or (now - bucket.window_start) >= window:
                self._buckets[key] = _Bucket(window_start=now, count=1)
                return

            bucket.count += 1
            if bucket.count > limit:
                raise AppHTTPException(
                    429,
                    "RATE_LIMITED",
                    f"Trop de requêtes (limite: {limit}/min).",
                    details={"limit_rpm": limit},
                )


rate_limiter = InMemoryRateLimiter()
