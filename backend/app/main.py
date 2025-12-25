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
from app.core.rate_limit import rate_limiter

from app.core.realtime import ConnectionManager
from app.api.ws import router as ws_router

"""
Application FastAPI (entrypoint).

Rôle (fonctionnel) :
- Configure l’application (settings, CORS, middlewares, routers).
- Centralise l’observabilité :
  - request_id propagé (X-Request-Id)
  - logs structurés JSON (timing, status, client_ip)
  - seuil de “slow request”
- Applique un rate-limit simple (optionnel) sur certains endpoints.
- Uniformise les erreurs côté client (format error_payload).
- Initialise le manager WebSocket (push temps réel).

Ce fichier ne contient pas de logique métier :
- La logique métier est dans app.services
- Les routes sont dans app.api
- Les composants transverses sont dans app.core
"""


# --- Force UTF-8 in Content-Type for JSON responses ---
class UTF8JSONResponse(JSONResponse):
    """Réponse JSON avec charset UTF-8 explicite (cohérent sur tous les endpoints)."""
    media_type = "application/json; charset=utf-8"


# --- Logging (niveau depuis .env si dispo) ---
LOG_LEVEL = getattr(settings, "LOG_LEVEL", "INFO")
setup_logging(LOG_LEVEL)

# logger principal projet
log = logging.getLogger("sentinelai")

# logger dédié observabilité HTTP (séparé du métier)
http_log = logging.getLogger("app.http")

# seuil slow request (ms)
SLOW_MS = int(getattr(settings, "SLOW_REQUEST_MS", 800))


def _split_origins(value: str) -> list[str]:
    """Parse une liste d’origines CORS depuis une string 'a,b,c'."""
    if not value:
        return []
    return [o.strip() for o in value.split(",") if o.strip()]


app = FastAPI(
    title=getattr(settings, "APP_NAME", "SentinelAI API"),
    debug=getattr(settings, "DEBUG", False),
    default_response_class=UTF8JSONResponse,
)

# WebSocket manager partagé (accessible via request.app.state.ws_manager)
app.state.ws_manager = ConnectionManager()

# --- CORS ---
origins = _split_origins(getattr(settings, "CORS_ORIGINS", ""))

# Origines par défaut en dev (Vite + React legacy)
default_dev_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins or default_dev_origins,
    allow_credentials=False,  # pas de cookies (API stateless)
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=[
        "Content-Type",
        "Authorization",
        "X-API-Key",
        "X-Actor",
        "X-Request-Id",
    ],
)

# --- Routers ---
app.include_router(api_router)
app.include_router(ws_router)


# --- Middleware observabilité : request_id + timing + logs structurés ---
@app.middleware("http")
async def request_observability(request: Request, call_next):
    # Prend le header s’il existe, sinon génère un UUID
    rid = ensure_request_id(request.headers.get("X-Request-Id"))
    request.state.request_id = rid

    start = time.perf_counter()
    response = None
    try:
        response = await call_next(request)
        return response
    finally:
        duration_ms = int((time.perf_counter() - start) * 1000)

        # Toujours renvoyer le request id au client
        try:
            if response is not None:
                response.headers["X-Request-Id"] = rid
        except Exception:
            pass

        # Slow request => WARNING, sinon INFO
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

        # Reset contextvar (propre en cas de réutilisation event loop / worker)
        set_request_id(None)


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """
    Rate-limit (optionnel) :
    - Ne bloque jamais les préflights CORS (OPTIONS).
    - S’applique uniquement sur certains chemins sensibles.
    - En cas de dépassement : renvoie un payload d’erreur standardisé.
    """
    if request.method == "OPTIONS":
        return await call_next(request)

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


# --- Error handlers : format standard, pas de stacktrace côté client ---
@app.exception_handler(AppHTTPException)
async def app_http_exception_handler(request: Request, exc: AppHTTPException):
    """Erreurs applicatives (AppHTTPException) -> payload standard."""
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
    """Erreurs HTTP natives (404, 405, etc.) -> payload standard."""
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
    """Erreurs de validation Pydantic -> 422 + details=exc.errors()."""
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
    """Fallback : toute exception non gérée -> 500 + log serveur."""
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
