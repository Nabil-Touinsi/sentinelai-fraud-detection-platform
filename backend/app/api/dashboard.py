from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import settings
from app.db.session import get_db
from app.schemas.dashboard import DashboardSummaryOut
from app.services.dashboard_service import get_dashboard_summary

"""
API Dashboard.

Rôle (fonctionnel) :
- Expose un endpoint de synthèse pour le front (KPI + séries + hotspots).
- Option simulate : permet d’injecter des transactions récentes pour faire bouger les chiffres en démo.
"""

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummaryOut)
async def dashboard_summary(
    db: AsyncSession = Depends(get_db),
    days: int = Query(30, ge=7, le=365),
    top_n: int = Query(8, ge=3, le=20),
    simulate: bool = Query(False),
    simulate_n: int = Query(3, ge=1, le=50),
):
    return await get_dashboard_summary(
        db=db,
        days=days,
        top_n=top_n,
        simulate=simulate,
        simulate_n=simulate_n,
        alert_threshold=settings.ALERT_THRESHOLD,
    )
