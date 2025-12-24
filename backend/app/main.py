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
from app.core.request_id import set_request_id, get_request_id, ensure_request_id
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

# logger principal projet (tu peux garder)
log = logging.getLogger("sentinelai")

# logger dédié observabilité HTTP (mieux séparé)
http_log = logging.getLogger("app.http")

# seuil slow request
SLOW_MS = int(getattr(settings, "SLOW_REQUEST_MS", 800))


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

# ✅ Dev origins (Vite 5173 + React 3000) si jamais CORS_ORIGINS est vide
default_dev_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins or default_dev_origins,
    allow_credentials=False,  # ✅ pas de cookies
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=[
        "Content-Type",
        "Authorization",
        "X-API-Key",
        "X-Actor",        # ✅ demandé
        "X-Request-Id",
    ],
)

# --- Routers ---
app.include_router(api_router)

# ✅ WebSocket router
app.include_router(ws_router)


# --- Middleware observabilité : request_id + timing + logs structurés ---
@app.middleware("http")
async def request_observability(request: Request, call_next):
    # ✅ prend le header si fourni, sinon génère
    rid = ensure_request_id(request.headers.get("X-Request-Id"))
    request.state.request_id = rid

    start = time.perf_counter()
    response = None
    try:
        response = await call_next(request)
        return response
    finally:
        duration_ms = int((time.perf_counter() - start) * 1000)

        # ✅ Toujours renvoyer le request id
        try:
            if response is not None:
                response.headers["X-Request-Id"] = rid
        except Exception:
            pass

        level = logging.WARNING if duration_ms >= SLOW_MS else logging.INFO
        http_log.log(
            level,
            "request",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": getattr(response, "status_code", None),
                "duration_ms": duration_ms,
                "client_ip": request.client.host if request.client else None,
            },
        )

        # ✅ reset contextvar (propre si reuse thread/event loop)
        set_request_id(None)


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    # ✅ IMPORTANT: ne jamais rate-limit / bloquer les préflights CORS
    if request.method == "OPTIONS":
        return await call_next(request)

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
