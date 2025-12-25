from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any

from .request_id import get_request_id

"""
Core Logging.

Rôle (fonctionnel) :
- Configure un logging JSON uniforme pour toute l’application (API + uvicorn).
- Injecte un request_id dans chaque log afin de corréler les événements d’une même requête.
- Supporte des “extras” structurés (method, path, status_code, duration_ms, actor, alert_id, etc.)
  pour faciliter le debug et l’observabilité (dashboard, traces, SIEM…).

Notes :
- Le format JSON est adapté aux agrégateurs de logs (ELK, Datadog, Loki, CloudWatch…).
- Le root logger est configuré et uvicorn est aligné sur le même handler.
"""


class RequestIdFilter(logging.Filter):
    """Ajoute request_id au LogRecord (valeur '-' si absent)."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id() or "-"
        return True


class JsonFormatter(logging.Formatter):
    """Formateur JSON pour logs structurés (1 event = 1 ligne JSON)."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "request_id": getattr(record, "request_id", "-"),
            "msg": record.getMessage(),
        }

        # Extras standardisés (si fournis via logger.info(..., extra={...}))
        for key in (
            "method",
            "path",
            "status_code",
            "duration_ms",
            "client_ip",
            "actor",
            "alert_id",
            "old_status",
            "new_status",
        ):
            if hasattr(record, key):
                payload[key] = getattr(record, key)

        # Stacktrace si exception attachée au record
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False)


def setup_logging(level: str = "INFO") -> None:
    """
    Initialise le logging global (root) en JSON et aligne uvicorn sur la même configuration.

    - Nettoie les handlers existants pour éviter les doublons (notamment avec --reload).
    - Configure un StreamHandler stdout + JsonFormatter + RequestIdFilter.
    """
    lvl = level.upper()

    root = logging.getLogger()
    root.setLevel(lvl)

    # Éviter doublons avec --reload (FastAPI/Uvicorn)
    if root.handlers:
        root.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(RequestIdFilter())
    root.addHandler(handler)

    # Aligner uvicorn logs sur le même handler
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        logger.handlers = root.handlers
        logger.setLevel(lvl)
