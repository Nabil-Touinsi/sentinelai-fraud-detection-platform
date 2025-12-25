from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import HTTPException

"""
Core Errors.

Rôle (fonctionnel) :
- Standardise le format des erreurs renvoyées par l’API (payload homogène).
- Fournit une exception applicative (AppHTTPException) pour lever des erreurs métier de façon cohérente.
- Facilite le debug et l’observabilité via des champs stables : code, status, request_id, timestamp, details.

Convention de réponse (exemple) :
{
  "error": {
    "code": "NOT_FOUND",
    "message": "Transaction introuvable",
    "status": 404,
    "request_id": "...",
    "timestamp": "...",
    "details": {...}
  }
}
"""


def now_iso() -> str:
    """Timestamp ISO-8601 en UTC (utilisé dans toutes les erreurs)."""
    return datetime.now(timezone.utc).isoformat()


def error_payload(
    *,
    code: str,
    message: str,
    status: int,
    request_id: str,
    details: Optional[Any] = None,
) -> Dict[str, Any]:
    """Construit un payload d’erreur homogène pour l’API."""
    payload: Dict[str, Any] = {
        "error": {
            "code": code,
            "message": message,
            "status": status,
            "request_id": request_id,
            "timestamp": now_iso(),
        }
    }
    if details is not None:
        payload["error"]["details"] = details
    return payload


class AppHTTPException(HTTPException):
    """
    Exception applicative standardisée.

    Usage :
    - Lever une erreur “métier” avec un code stable et un message explicite.
    - Laisser la couche API/middlewares produire une réponse cohérente.

    Exemple :
        raise AppHTTPException(404, "NOT_FOUND", "Transaction introuvable")
    """

    def __init__(self, status_code: int, code: str, message: str, details: Any = None):
        # On conserve le format attendu par la couche de gestion d’erreurs de l’app
        super().__init__(status_code=status_code, detail={"code": code, "message": message, "details": details})
        