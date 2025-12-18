import logging
import sys

from .request_id import get_request_id


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id() or "-"
        return True


def setup_logging(level: str = "INFO") -> None:
    lvl = level.upper()

    root = logging.getLogger()
    root.setLevel(lvl)

    # éviter doublons avec --reload
    if root.handlers:
        root.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | rid=%(request_id)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    handler.addFilter(RequestIdFilter())
    root.addHandler(handler)

    # aligner uvicorn logs sur le même format
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        logger.handlers = root.handlers
        logger.setLevel(lvl)
