from fastapi import APIRouter
from ..core.settings import settings

router = APIRouter()

@router.get("/health")
def health():
    return {
        "status": "ok",
        "env": settings.ENV,
        "threshold": settings.ALERT_THRESHOLD,
    }
