from __future__ import annotations

import secrets
from typing import Optional

from fastapi import Request

from app.core.settings import settings
from app.core.errors import AppHTTPException

"""
Core Security (API Key).

Rôle (fonctionnel) :
- Fournit une authentification simple par API key (mode démo).
- Supporte deux formats de headers :
  - Authorization: Bearer <token>
  - X-API-Key: <token>

Comportement :
- Si API_KEY est configurée : la clé est requise.
- Si API_KEY est vide et ENV != prod : bypass (pratique en dev / local).
- Si API_KEY est vide et ENV = prod : erreur 500 (configuration serveur invalide).

Notes :
- compare_digest() est utilisé pour éviter les comparaisons sensibles au timing.
- Ce mécanisme est volontairement simple : en production, on préférera OAuth/JWT + RBAC, etc.
"""


def _extract_token(request: Request) -> Optional[str]:
    """Extrait un token depuis Authorization Bearer ou X-API-Key (si présent)."""
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
    Dépendance FastAPI : vérifie la présence/validité d’une API key.

    Usage :
    - À brancher sur les routes sensibles (Depends(require_api_key)) ou en middleware.
    - Ne retourne rien : lève AppHTTPException si non autorisé.
    """
    expected = getattr(settings, "API_KEY", "") or ""

    if not expected:
        # En prod, une API key manquante est une mauvaise config serveur
        if str(getattr(settings, "ENV", "dev")).lower() == "prod":
            raise AppHTTPException(
                500,
                "SERVER_MISCONFIG",
                "API_KEY manquante côté serveur",
            )
        # En dev/local : on bypass pour faciliter les tests
        return

    token = _extract_token(request)
    if not token or not secrets.compare_digest(token, expected):
        raise AppHTTPException(
            401,
            "UNAUTHORIZED",
            "Clé API invalide ou manquante",
        )
