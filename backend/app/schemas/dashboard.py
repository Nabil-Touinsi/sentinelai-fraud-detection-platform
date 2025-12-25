from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, ConfigDict

"""
Schemas Dashboard (Pydantic).

Rôle (fonctionnel) :
- Définit le contrat de réponse pour les endpoints “dashboard”.
- Structure les données nécessaires au front :
  - KPI (compteurs + moyennes),
  - séries temporelles (par jour),
  - hotspots (zones / catégories / marchands) pour cartes et classements.

Notes :
- Ces schémas sont des “DTO” de lecture : ils agrègent des données calculées (pas des lignes DB).
- extra="forbid" sur DashboardSummaryOut impose un contrat strict côté API.
"""


class DashboardKpis(BaseModel):
    """Indicateurs clés agrégés (totaux + fenêtre glissante)."""
    transactions_total: int
    transactions_window: int
    alerts_total: int
    alerts_open: int
    alerts_critical: int
    avg_risk_score_window: Optional[float] = None


class DashboardDayPoint(BaseModel):
    """Point journalier pour la série temporelle (courbe)."""
    date: str  # "YYYY-MM-DD"
    transactions: int
    alerts: int
    avg_score: Optional[float] = None


class HotspotItem(BaseModel):
    """Item “hotspot” : une clé (zone/catégorie/merchant) + volume + score moyen."""
    key: str
    count: int
    avg_score: Optional[float] = None


class DashboardHotspots(BaseModel):
    """Hotspots par dimensions principales (utilisés par la carte + tableaux)."""
    arrondissements: List[HotspotItem]
    categories: List[HotspotItem]
    merchants: List[HotspotItem]


class DashboardSeries(BaseModel):
    """Séries temporelles du dashboard."""
    days: List[DashboardDayPoint]


class DashboardSummaryOut(BaseModel):
    """Réponse complète du dashboard : KPI + séries + hotspots."""
    kpis: DashboardKpis
    series: DashboardSeries
    hotspots: DashboardHotspots

    model_config = ConfigDict(extra="forbid")
