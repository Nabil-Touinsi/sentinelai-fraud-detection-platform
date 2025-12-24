from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, ConfigDict


class DashboardKpis(BaseModel):
    transactions_total: int
    transactions_window: int
    alerts_total: int
    alerts_open: int
    alerts_critical: int
    avg_risk_score_window: Optional[float] = None


class DashboardDayPoint(BaseModel):
    date: str  # "YYYY-MM-DD"
    transactions: int
    alerts: int
    avg_score: Optional[float] = None


class HotspotItem(BaseModel):
    key: str
    count: int
    avg_score: Optional[float] = None


class DashboardHotspots(BaseModel):
    arrondissements: List[HotspotItem]
    categories: List[HotspotItem]
    merchants: List[HotspotItem]


class DashboardSeries(BaseModel):
    days: List[DashboardDayPoint]


class DashboardSummaryOut(BaseModel):
    kpis: DashboardKpis
    series: DashboardSeries
    hotspots: DashboardHotspots

    model_config = ConfigDict(extra="forbid")
