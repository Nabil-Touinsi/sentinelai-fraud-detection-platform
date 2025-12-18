from contextvars import ContextVar
from typing import Optional

_request_id: ContextVar[Optional[str]] = ContextVar("request_id", default=None)

def set_request_id(value: str) -> None:
    _request_id.set(value)

def get_request_id() -> Optional[str]:
    return _request_id.get()
