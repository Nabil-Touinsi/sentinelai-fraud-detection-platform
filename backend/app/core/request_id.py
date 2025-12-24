from __future__ import annotations

import uuid
from contextvars import ContextVar

_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)

def set_request_id(rid: str | None) -> None:
    _request_id.set(rid)

def get_request_id() -> str | None:
    return _request_id.get()

def ensure_request_id(incoming: str | None = None) -> str:
    rid = (incoming or "").strip() or str(uuid.uuid4())
    set_request_id(rid)
    return rid
