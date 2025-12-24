from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Dict, List, Tuple

from sqlalchemy import func, select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import settings
from app.models.transaction import Transaction
from app.models.alert import Alert
from app.models.risk_score import RiskScore
from app.schemas.dashboard import (
    DashboardSummaryOut,
    DashboardKpis,
    DashboardSeries,
    DashboardDayPoint,
    DashboardHotspots,
    HotspotItem,
)

CLOSED_STATUSES = {"closed", "CLOTURE"}  # tolère l’état actuel + l’état final (P1)
DEFAULT_CRITICAL_SCORE = 85


def _date_range(days: int) -> Tuple[datetime, List[date]]:
    """Retourne (start_dt_utc, list_of_dates_inclusive)."""
    end_d = datetime.now(timezone.utc).date()
    start_d = end_d - timedelta(days=days - 1)
    start_dt = datetime.combine(start_d, time.min, tzinfo=timezone.utc)
    all_days = [start_d + timedelta(days=i) for i in range(days)]
    return start_dt, all_days


async def get_dashboard_summary(db: AsyncSession, days: int = 30, top_n: int = 8) -> DashboardSummaryOut:
    start_dt, day_list = _date_range(days)

    critical_score = DEFAULT_CRITICAL_SCORE
    threshold = getattr(settings, "ALERT_THRESHOLD", 70)
    if threshold and threshold > critical_score:
        critical_score = threshold  # si ton seuil alerte est déjà très haut

    # -------------------
    # KPIs
    # -------------------
    transactions_total = (await db.execute(select(func.count()).select_from(Transaction))).scalar_one()
    transactions_window = (
        await db.execute(
            select(func.count()).select_from(Transaction).where(Transaction.occurred_at >= start_dt)
        )
    ).scalar_one()

    alerts_total = (await db.execute(select(func.count()).select_from(Alert))).scalar_one()
    alerts_open = (
        await db.execute(
            select(func.count()).select_from(Alert).where(~Alert.status.in_(CLOSED_STATUSES))
        )
    ).scalar_one()

    alerts_critical = (
        await db.execute(
            select(func.count()).select_from(Alert).where(Alert.score_snapshot >= critical_score)
        )
    ).scalar_one()

    avg_risk_score_window = (
        await db.execute(
            select(func.avg(RiskScore.score)).where(RiskScore.created_at >= start_dt)
        )
    ).scalar_one()

    kpis = DashboardKpis(
        transactions_total=transactions_total,
        transactions_window=transactions_window,
        alerts_total=alerts_total,
        alerts_open=alerts_open,
        alerts_critical=alerts_critical,
        avg_risk_score_window=float(avg_risk_score_window) if avg_risk_score_window is not None else None,
    )

    # -------------------
    # SERIES (par jour)
    # -------------------
    # Transactions/day
    tx_rows = (
        await db.execute(
            select(
                func.date_trunc("day", Transaction.occurred_at).label("day"),
                func.count(Transaction.id).label("cnt"),
            )
            .where(Transaction.occurred_at >= start_dt)
            .group_by("day")
            .order_by("day")
        )
    ).all()
    tx_map: Dict[str, int] = {r.day.date().isoformat(): int(r.cnt) for r in tx_rows}

    # Alerts/day
    al_rows = (
        await db.execute(
            select(
                func.date_trunc("day", Alert.created_at).label("day"),
                func.count(Alert.id).label("cnt"),
            )
            .where(Alert.created_at >= start_dt)
            .group_by("day")
            .order_by("day")
        )
    ).all()
    al_map: Dict[str, int] = {r.day.date().isoformat(): int(r.cnt) for r in al_rows}

    # Avg score/day
    rs_rows = (
        await db.execute(
            select(
                func.date_trunc("day", RiskScore.created_at).label("day"),
                func.avg(RiskScore.score).label("avg_score"),
            )
            .where(RiskScore.created_at >= start_dt)
            .group_by("day")
            .order_by("day")
        )
    ).all()
    rs_map: Dict[str, float] = {
        r.day.date().isoformat(): float(r.avg_score) for r in rs_rows if r.avg_score is not None
    }

    points: List[DashboardDayPoint] = []
    for d in day_list:
        key = d.isoformat()
        points.append(
            DashboardDayPoint(
                date=key,
                transactions=tx_map.get(key, 0),
                alerts=al_map.get(key, 0),
                avg_score=rs_map.get(key),
            )
        )

    series = DashboardSeries(days=points)

    # -------------------
    # HOTSPOTS (top N)
    # -------------------
    # arrondissements
    arr_rows = (
        await db.execute(
            select(
                Transaction.arrondissement.label("key"),
                func.count(Alert.id).label("cnt"),
                func.avg(Alert.score_snapshot).label("avg_score"),
            )
            .join(Transaction, Transaction.id == Alert.transaction_id)
            .where(Alert.created_at >= start_dt)
            .where(Transaction.arrondissement.is_not(None))
            .group_by("key")
            .order_by(desc("cnt"))
            .limit(top_n)
        )
    ).all()

    # categories
    cat_rows = (
        await db.execute(
            select(
                Transaction.merchant_category.label("key"),
                func.count(Alert.id).label("cnt"),
                func.avg(Alert.score_snapshot).label("avg_score"),
            )
            .join(Transaction, Transaction.id == Alert.transaction_id)
            .where(Alert.created_at >= start_dt)
            .group_by("key")
            .order_by(desc("cnt"))
            .limit(top_n)
        )
    ).all()

    # merchants
    mer_rows = (
        await db.execute(
            select(
                Transaction.merchant_name.label("key"),
                func.count(Alert.id).label("cnt"),
                func.avg(Alert.score_snapshot).label("avg_score"),
            )
            .join(Transaction, Transaction.id == Alert.transaction_id)
            .where(Alert.created_at >= start_dt)
            .group_by("key")
            .order_by(desc("cnt"))
            .limit(top_n)
        )
    ).all()

    hotspots = DashboardHotspots(
        arrondissements=[
            HotspotItem(key=str(r.key), count=int(r.cnt), avg_score=float(r.avg_score) if r.avg_score is not None else None)
            for r in arr_rows
        ],
        categories=[
            HotspotItem(key=str(r.key), count=int(r.cnt), avg_score=float(r.avg_score) if r.avg_score is not None else None)
            for r in cat_rows
        ],
        merchants=[
            HotspotItem(key=str(r.key), count=int(r.cnt), avg_score=float(r.avg_score) if r.avg_score is not None else None)
            for r in mer_rows
        ],
    )

    return DashboardSummaryOut(kpis=kpis, series=series, hotspots=hotspots)
