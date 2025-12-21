from __future__ import annotations

import time
import uuid
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.router import api_router
from app.core.settings import settings
from app.core.logging import setup_logging
from app.core.errors import error_payload, AppHTTPException
from app.core.request_id import set_request_id, get_request_id
from app.core.rate_limit import rate_limiter  # ✅ NEW

# ✅ realtime WS manager + WS router
from app.core.realtime import ConnectionManager
from app.api.ws import router as ws_router


# --- Force UTF-8 in Content-Type for JSON responses ---
class UTF8JSONResponse(JSONResponse):
    media_type = "application/json; charset=utf-8"


# --- Logging (niveau depuis .env si dispo) ---
LOG_LEVEL = getattr(settings, "LOG_LEVEL", "INFO")
setup_logging(LOG_LEVEL)
log = logging.getLogger("sentinelai")


def _split_origins(value: str) -> list[str]:
    if not value:
        return []
    return [o.strip() for o in value.split(",") if o.strip()]


app = FastAPI(
    title=getattr(settings, "APP_NAME", "SentinelAI API"),
    debug=getattr(settings, "DEBUG", False),
    default_response_class=UTF8JSONResponse,  # ✅ UTF-8 everywhere
)

# ✅ init WebSocket manager (accessible via request.app.state.ws_manager)
app.state.ws_manager = ConnectionManager()

# --- CORS ---
origins = _split_origins(getattr(settings, "CORS_ORIGINS", ""))

# Vite dev (5173) si jamais CORS_ORIGINS est vide
default_dev_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins or default_dev_origins,
    allow_credentials=False,  # ✅ pas de cookies -> plus safe
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-API-Key", "X-Request-Id"],
)

# --- Routers ---
app.include_router(api_router)

# ✅ WebSocket router
app.include_router(ws_router)


# --- Middleware request_id + logs ---
@app.middleware("http")
async def request_context_and_logs(request: Request, call_next):
    rid = request.headers.get("x-request-id") or str(uuid.uuid4())

    # ✅ accessible via tes helpers + via request.state (utile pour deps/security)
    set_request_id(rid)
    request.state.request_id = rid

    start = time.time()
    response = await call_next(request)
    duration_ms = int((time.time() - start) * 1000)

    response.headers["x-request-id"] = rid
    log.info("%s %s -> %s (%sms)", request.method, request.url.path, response.status_code, duration_ms)
    return response


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    # limiter seulement les endpoints REST sensibles
    if request.url.path.startswith(("/transactions", "/alerts", "/score")):
        try:
            rate_limiter.check(request)
        except AppHTTPException as exc:
            rid = getattr(request.state, "request_id", None) or get_request_id() or str(uuid.uuid4())
            detail = exc.detail if isinstance(exc.detail, dict) else {}

            code = str(detail.get("code", "RATE_LIMITED"))
            message = str(detail.get("message", "Trop de requêtes"))
            details = detail.get("details", None)

            return UTF8JSONResponse(
                status_code=exc.status_code,
                content=error_payload(
                    code=code,
                    message=message,
                    status=exc.status_code,
                    request_id=rid,
                    details=details,
                ),
            )

    return await call_next(request)



# --- Error handlers (format standard, no stacktrace côté client) ---
@app.exception_handler(AppHTTPException)
async def app_http_exception_handler(request: Request, exc: AppHTTPException):
    rid = getattr(request.state, "request_id", None) or get_request_id() or str(uuid.uuid4())
    detail = exc.detail if isinstance(exc.detail, dict) else {}

    code = str(detail.get("code", "HTTP_ERROR"))
    message = str(detail.get("message", "Erreur HTTP"))
    details = detail.get("details", None)

    return UTF8JSONResponse(
        status_code=exc.status_code,
        content=error_payload(code=code, message=message, status=exc.status_code, request_id=rid, details=details),
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    rid = getattr(request.state, "request_id", None) or get_request_id() or str(uuid.uuid4())

    if isinstance(exc.detail, dict):
        code = str(exc.detail.get("code", "HTTP_ERROR"))
        message = str(exc.detail.get("message", "Erreur HTTP"))
        details = exc.detail.get("details", None)
    else:
        code = "NOT_FOUND" if exc.status_code == 404 else "HTTP_ERROR"
        message = str(exc.detail)
        details = None

    return UTF8JSONResponse(
        status_code=exc.status_code,
        content=error_payload(code=code, message=message, status=exc.status_code, request_id=rid, details=details),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    rid = getattr(request.state, "request_id", None) or get_request_id() or str(uuid.uuid4())
    return UTF8JSONResponse(
        status_code=422,
        content=error_payload(
            code="VALIDATION_ERROR",
            message="Requête invalide",
            status=422,
            request_id=rid,
            details=exc.errors(),
        ),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    rid = getattr(request.state, "request_id", None) or get_request_id() or str(uuid.uuid4())
    log.exception("Unhandled error: %s", exc)

    return UTF8JSONResponse(
        status_code=500,
        content=error_payload(
            code="INTERNAL_ERROR",
            message="Erreur interne du serveur",
            status=500,
            request_id=rid,
        ),
    )
