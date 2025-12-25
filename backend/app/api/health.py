from fastapi import APIRouter

from app.core.settings import settings

"""
API Health.

Rôle (fonctionnel) :
- Endpoint simple pour vérifier que l’API répond.
- Expose quelques infos utiles en démo (env, seuil d’alerte).
"""

router = APIRouter()


@router.get("/health")
def health():
    return {
        "status": "ok",
        "env": settings.ENV,
        "threshold": settings.ALERT_THRESHOLD,
    }
