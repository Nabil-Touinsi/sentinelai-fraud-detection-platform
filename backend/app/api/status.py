from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.core.settings import settings

"""
API System Status.

Rôle (fonctionnel) :
- Expose un endpoint de statut “healthcheck” pour la plateforme.
- Vérifie la disponibilité de la base (requête simple).
- Expose l’état du “modèle” côté API (version déclarée dans les settings).
- Fournit une information de fraîcheur via la date du dernier score (risk_scores).
"""

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/status")
async def system_status(db: AsyncSession = Depends(get_db)):
    # 1) DB check (requête minimale)
    db_ok = True
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        db_ok = False

    # 2) Model check 
    # On expose une "version" si elle existe dans settings,
    # sinon on met une valeur fallback.
    model_version = getattr(settings, "MODEL_VERSION", None) or "unknown"
    models_ok = True

    # 3) Last update (dernier score)
    last_update = None
    try:
        r = await db.execute(text("SELECT MAX(created_at) AS last_update FROM risk_scores"))
        row = r.mappings().first()
        last_update = row["last_update"].isoformat() if row and row["last_update"] else None
    except Exception:
        last_update = None

    # Réponse (format constant) pour monitoring / UI
    return {
        "ok": bool(db_ok and models_ok),
        "db": {"ok": db_ok},
        "models": {"ok": models_ok, "version": model_version},
        "alert_threshold": getattr(settings, "ALERT_THRESHOLD", None),
        "last_update": last_update,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
