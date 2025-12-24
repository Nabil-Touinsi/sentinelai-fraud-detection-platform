from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any

from .request_id import get_request_id


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id() or "-"
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "request_id": getattr(record, "request_id", "-"),
            "msg": record.getMessage(),
        }

        # extras (si fournis via logger.info(..., extra={...}))
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

        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False)


def setup_logging(level: str = "INFO") -> None:
    lvl = level.upper()

    root = logging.getLogger()
    root.setLevel(lvl)

    # éviter doublons avec --reload
    if root.handlers:
        root.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(RequestIdFilter())
    root.addHandler(handler)

    # aligner uvicorn logs sur le même handler
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        logger.handlers = root.handlers
        logger.setLevel(lvl)
