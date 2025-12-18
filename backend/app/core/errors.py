from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import HTTPException


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def error_payload(
    *,
    code: str,
    message: str,
    status: int,
    request_id: str,
    details: Optional[Any] = None,
) -> Dict[str, Any]:
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
    Exemple: raise AppHTTPException(404, "NOT_FOUND", "Transaction introuvable")
    """

    def __init__(self, status_code: int, code: str, message: str, details: Any = None):
        super().__init__(status_code=status_code, detail={"code": code, "message": message, "details": details})
