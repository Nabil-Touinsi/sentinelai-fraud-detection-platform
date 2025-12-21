from __future__ import annotations

import secrets
from typing import Optional

from fastapi import Request

from app.core.settings import settings
from app.core.errors import AppHTTPException


def _extract_token(request: Request) -> Optional[str]:
    # Authorization: Bearer <token>
    auth = request.headers.get("authorization")
    if auth:
        parts = auth.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            return parts[1].strip()

    # X-API-Key: <token>
    x_api_key = request.headers.get("x-api-key")
    if x_api_key:
        return x_api_key.strip()

    return None


async def require_api_key(request: Request) -> None:
    """
    Auth simple pour la démo.
    - Si API_KEY est configurée -> obligatoire
    - Si API_KEY est vide et ENV != prod -> bypass (pratique en dev)
    - Si API_KEY est vide et ENV=prod -> erreur serveur (misconfig)
    """
    expected = getattr(settings, "API_KEY", "") or ""

    if not expected:
        if str(getattr(settings, "ENV", "dev")).lower() == "prod":
            raise AppHTTPException(
                500,
                "SERVER_MISCONFIG",
                "API_KEY manquante côté serveur",
            )
        return

    token = _extract_token(request)
    if not token or not secrets.compare_digest(token, expected):
        raise AppHTTPException(
            401,
            "UNAUTHORIZED",
            "Clé API invalide ou manquante",
        )
