from fastapi import APIRouter

from .health import router as health_router
from .transactions import router as transactions_router

from app.api.score import router as score_router
from app.api.alerts import router as alerts_router
from app.api.status import router as status_router
from app.api.dashboard import router as dashboard_router

"""
Router principal de l’API.

Rôle (fonctionnel) :
- Regroupe les routeurs par domaine (health, transactions, scoring, alertes, dashboard, etc.)
- Sert de point d’entrée unique pour l’inclusion dans l’application FastAPI.
"""

api_router = APIRouter()

api_router.include_router(health_router, tags=["health"])
api_router.include_router(transactions_router, tags=["transactions"])
api_router.include_router(score_router)
api_router.include_router(alerts_router)
api_router.include_router(status_router)
api_router.include_router(dashboard_router)
