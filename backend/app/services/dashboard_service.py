from __future__ import annotations

import random
import re
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alert import Alert
from app.models.risk_score import RiskScore
from app.models.transaction import Transaction
from app.schemas.dashboard import (
    DashboardDayPoint,
    DashboardHotspots,
    DashboardKpis,
    DashboardSeries,
    DashboardSummaryOut,
    HotspotItem,
)
from app.services.scoring_service import ScoringService

"""
Dashboard Service.

Rôle (fonctionnel) :
- Calcule la “vue agrégée” du dashboard (1 endpoint = 1 payload complet) :
  - KPI (compteurs / stats globales)
  - séries temporelles (par jour)
  - hotspots (arrondissements / catégories / marchands)

Optionnel :
- Mode simulation : injecte des transactions “live” puis les score, afin que les chiffres bougent
  sans dépendre d’une source externe. Utile en démo / local.

Notes :
- L’objectif est que le front consomme un objet stable (DashboardSummaryOut) sans assembler
  plusieurs endpoints.
- Le heatmap arrondissements renvoie toujours 1..20 (même si count=0) pour conserver l’affichage
  “calme / moyen / chaud” sur la carte.
"""

# -----------------------------
# Helpers (arrondissements)
# -----------------------------
_ARR_RE = re.compile(r"(\d{1,2})")


def _parse_arr_num(value: Optional[str]) -> Optional[int]:
    """Extrait un numéro 1..20 depuis une valeur texte (ex: '75011', '11e', '11')."""
    if not value:
        return None
    m = _ARR_RE.search(str(value))
    if not m:
        return None
    n = int(m.group(1))
    return n if 1 <= n <= 20 else None


def _arr_label(n: int) -> str:
    """Libellé d’arrondissement (format côté UI)."""
    return str(n)


def _date_range(days: int) -> Tuple[datetime, List[date]]:
    """Retourne (start_dt UTC, liste des dates inclusives) sur les N derniers jours."""
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=days)
    start_date = start.date()
    dates = [start_date + timedelta(days=i) for i in range(days + 1)]
    return start, dates


# -----------------------------
# Simulator (transactions live)
# -----------------------------
# Catégories simulées (variées) pour rendre les listes/graphes crédibles en démo
_SIM_CATEGORIES = [
    "ecommerce", "electronics", "hotel", "groceries", "restaurant", "travel", "pharmacy", "fuel",
    "luxury", "fashion", "beauty", "sports", "entertainment", "streaming", "gaming", "subscriptions",
    "telecom", "utilities", "insurance", "banking", "crypto", "investment", "atm", "cash_withdrawal",
    "transport", "rideshare", "delivery", "courier", "parking", "toll", "car_rental",
    "airline", "rail", "metro", "bus", "taxi",
    "home_improvement", "furniture", "garden", "hardware",
    "education", "books", "stationery",
    "healthcare", "clinic", "dental", "optics",
    "charity", "donation",
    "marketplace", "digital_goods", "saas",
    "nightlife", "bar", "cafe",
    "pet_supplies", "baby", "kids",
    "jewelry", "watches",
    "photography", "music", "events",
    "government", "fees", "fines",
    "international_transfer", "remittance",
]

# Marchands fallback (si catégorie non mappée)
_SIM_MERCHANTS = [
    "Monoprix", "Carrefour", "Auchan", "Intermarché", "Leclerc", "Franprix", "Casino", "Picard",
    "FNAC", "Darty", "Boulanger", "Cdiscount", "Amazon", "Apple Store", "Samsung Store",
    "Zara", "H&M", "Uniqlo", "Decathlon", "Nike", "Adidas", "Sephora", "Yves Rocher",
    "Ikea", "Leroy Merlin", "Castorama", "Brico Dépôt", "Conforama",
    "Uber", "Bolt", "Free Now", "G7", "Heetch",
    "Deliveroo", "Uber Eats", "Just Eat", "Glovo",
    "SNCF Connect", "RATP", "Air France", "EasyJet", "Ryanair", "Booking.com", "Airbnb", "Expedia",
    "TotalEnergies", "Shell", "Esso",
    "Orange", "SFR", "Bouygues Telecom", "Free Mobile",
    "EDF", "Engie", "Veolia",
    "Netflix", "Spotify", "Deezer", "Canal+", "Disney+",
    "PlayStation Store", "Xbox Store", "Steam",
    "Doctolib", "Pharmacie Lafayette", "Optic 2000",
    "AXA", "MAIF", "Allianz",
    "La Poste", "Mondial Relay", "Chronopost",
    "Tabac Presse", "PMU", "FDJ",
]

# Mapping cohérent : catégorie -> marchands possibles (meilleure crédibilité démo)
_SIM_MERCHANTS_BY_CAT: Dict[str, List[str]] = {
    # --- e-commerce / digital
    "ecommerce": ["Amazon", "Cdiscount", "AliExpress", "Fnac.com", "Apple Store", "Samsung Store"],
    "marketplace": ["Amazon", "Leboncoin", "Vinted"],
    "digital_goods": ["PlayStation Store", "Xbox Store", "Steam"],
    "saas": ["Microsoft", "Adobe", "Notion", "Atlassian"],
    "streaming": ["Netflix", "Disney+", "Canal+", "Deezer", "Spotify"],
    "gaming": ["PlayStation Store", "Xbox Store", "Steam"],

    # --- retail
    "electronics": ["FNAC", "Darty", "Boulanger", "Apple Store", "Samsung Store"],
    "fashion": ["Zara", "H&M", "Uniqlo", "Nike", "Adidas"],
    "beauty": ["Sephora", "Yves Rocher"],
    "sports": ["Decathlon", "Nike", "Adidas"],
    "luxury": ["Galeries Lafayette", "Printemps", "Louis Vuitton"],

    # --- food / groceries
    "groceries": ["Monoprix", "Carrefour", "Auchan", "Intermarché", "Leclerc", "Franprix", "Picard", "Casino"],
    "restaurant": ["McDonald's", "Burger King", "KFC", "Big Fernand", "Le Bistrot du Coin"],
    "cafe": ["Starbucks", "Café de Flore", "Café du Coin"],
    "bar": ["Bar du Coin", "Pub", "L'Apéro"],
    "nightlife": ["Rex Club", "La Machine", "Club Local"],

    # --- transport / travel
    "transport": ["RATP", "SNCF Connect"],
    "metro": ["RATP"],
    "bus": ["RATP"],
    "rail": ["SNCF Connect"],
    "airline": ["Air France", "EasyJet", "Ryanair"],
    "travel": ["Expedia", "Booking.com", "Airbnb"],
    "hotel": ["Booking.com", "Accor", "Airbnb", "Expedia"],

    "rideshare": ["Uber", "Bolt", "Heetch", "Free Now"],
    "taxi": ["G7", "Uber", "Bolt"],
    "delivery": ["Deliveroo", "Uber Eats", "Just Eat", "Glovo"],
    "courier": ["Chronopost", "Mondial Relay", "La Poste"],
    "parking": ["Indigo", "Vinci Park"],
    "toll": ["Vinci Autoroutes", "Sanef"],
    "car_rental": ["Hertz", "Avis", "Europcar", "Sixt"],

    # --- utilities / telecom
    "utilities": ["EDF", "Engie", "Veolia"],
    "telecom": ["Orange", "SFR", "Bouygues Telecom", "Free Mobile"],
    "subscriptions": ["Netflix", "Spotify", "Disney+", "Canal+"],

    # --- health
    "pharmacy": ["Pharmacie Lafayette", "Pharmacie du Coin"],
    "healthcare": ["Doctolib", "Centre Médical"],
    "clinic": ["Centre Médical", "Clinique Privée"],
    "dental": ["Cabinet Dentaire", "Doctolib"],
    "optics": ["Optic 2000", "Afflelou"],

    # --- finance / insurance / transfers
    "insurance": ["AXA", "MAIF", "Allianz"],
    "banking": ["BNP Paribas", "Société Générale", "Crédit Agricole"],
    "atm": ["ATM - Banque"],
    "cash_withdrawal": ["ATM - Banque"],
    "international_transfer": ["Western Union", "MoneyGram", "La Poste"],
    "remittance": ["Western Union", "MoneyGram", "La Poste"],
    "crypto": ["Coinbase", "Binance"],
    "investment": ["Boursorama", "Degiro"],

    # --- home
    "home_improvement": ["Leroy Merlin", "Castorama", "Brico Dépôt"],
    "hardware": ["Leroy Merlin", "Castorama", "Brico Dépôt"],
    "furniture": ["Ikea", "Conforama", "Leroy Merlin"],
    "garden": ["Truffaut", "Jardiland"],

    # --- education / culture
    "books": ["FNAC", "Librairie du Coin"],
    "stationery": ["Bureau Vallée", "Staples"],
    "education": ["Udemy", "Coursera"],

    # --- misc
    "fuel": ["TotalEnergies", "Shell", "Esso"],
    "charity": ["Croix-Rouge", "UNICEF"],
    "donation": ["UNICEF", "Médecins Sans Frontières"],
    "government": ["Service Public", "Impots.gouv"],
    "fees": ["Service Public"],
    "fines": ["Service Public"],
    "events": ["Ticketmaster", "Fnac Spectacles"],
    "music": ["Spotify", "Deezer"],
    "pet_supplies": ["Maxi Zoo", "Animalis"],
    "baby": ["Orchestra", "Bébé 9"],
    "kids": ["King Jouet", "Oxybul"],
    "jewelry": ["Histoire d'Or", "Pandora"],
    "watches": ["Swatch", "Seiko"],
    "photography": ["FNAC", "Darty"],
}

# Canaux simulés (si non online)
_SIM_CHANNELS = ["card_present", "online", "mobile", "transfer"]


def _pick_merchant_for_category(cat: str) -> str:
    """
    Choisit un marchand cohérent avec la catégorie.

    - Si la catégorie est mappée : choix dans la pool dédiée.
    - Sinon : fallback sur une liste générique.
    """
    pool = _SIM_MERCHANTS_BY_CAT.get(cat)
    if pool:
        return random.choice(pool)
    return random.choice(_SIM_MERCHANTS)


async def _score_and_maybe_alert(db: AsyncSession, tx: Transaction, *, threshold: int) -> None:
    """
    Pipeline “démo live” :
    - Score la transaction via ScoringService (upsert risk_scores).
    - Crée ou met à jour une alerte si score >= threshold.

    Notes :
    - On respecte la contrainte 1 alerte max par risk_score (unique=True côté modèle Alert).
    - Pas d’historique ici : ce helper vise la simplicité pour “faire bouger” le dashboard.
    """
    scoring = ScoringService()
    result = await scoring.score_and_persist(db, tx)

    # Retrouver le RiskScore upserté (1:1 avec transaction)
    rs = (
        (await db.execute(select(RiskScore).where(RiskScore.transaction_id == tx.id)))
        .scalars()
        .first()
    )
    if not rs:
        return

    if int(result.score) >= int(threshold):
        # 1 alerte max par risk_score (unique=True)
        existing = (
            (await db.execute(select(Alert).where(Alert.risk_score_id == rs.id)))
            .scalars()
            .first()
        )

        now = datetime.now(timezone.utc)
        if existing:
            # Mise à jour snapshot si le score change
            if int(existing.score_snapshot) != int(result.score):
                existing.score_snapshot = int(result.score)
                existing.updated_at = now
                db.add(existing)
        else:
            # Création d’une alerte
            alert = Alert(
                transaction_id=tx.id,
                risk_score_id=rs.id,
                score_snapshot=int(result.score),
                status="open",
                reason="Auto-alert: score >= threshold",
                created_at=now,
                updated_at=now,
            )
            db.add(alert)

        await db.commit()


async def _simulate_transactions(
    db: AsyncSession,
    *,
    n: int = 3,
    burst_minutes: int = 5,
    threshold: int,
) -> int:
    """
    Génère des transactions “live” pour la démo.

    - Insère n transactions (occurred_at proche de now).
    - Score chaque transaction et déclenche des alertes si nécessaire.
    - merchant_name est choisi de façon cohérente avec merchant_category.
    """
    if n <= 0:
        return 0

    now = datetime.now(timezone.utc)
    created: List[Transaction] = []

    for _ in range(n):
        arr = random.randint(1, 20)

        # On choisit d'abord la catégorie, puis un marchand cohérent
        cat = random.choice(_SIM_CATEGORIES)
        merchant = _pick_merchant_for_category(cat)

        # Montant de base
        base_amount = random.uniform(5, 250)

        # Ajustements par catégories “chères”
        if cat in {"electronics", "hotel", "travel", "luxury", "car_rental"}:
            base_amount *= random.uniform(2.5, 10)

        # Ajustements par marchands “chers”
        if merchant in {"Apple Store", "Amazon", "Booking.com", "Air France", "Hertz", "Avis"}:
            base_amount *= random.uniform(1.2, 2.3)

        # Petite probabilité de gros outlier (rend le flux plus “réel”)
        if cat in {"ecommerce", "luxury", "investment", "crypto"} and random.random() < 0.05:
            base_amount *= random.uniform(5, 15)

        occurred_at = now - timedelta(minutes=random.randint(0, max(1, burst_minutes)))

        # Online plus probable pour certaines catégories
        online_bias = 0.35
        if cat in {"ecommerce", "streaming", "gaming", "digital_goods", "saas", "marketplace"}:
            online_bias = 0.8
        elif cat in {"rideshare", "delivery", "travel"}:
            online_bias = 0.6

        is_online = random.random() < online_bias
        channel = "online" if is_online else random.choice(_SIM_CHANNELS)

        tx = Transaction(
            occurred_at=occurred_at,
            created_at=now,
            amount=round(float(base_amount), 2),
            currency="EUR",
            merchant_name=merchant,
            merchant_category=cat,
            arrondissement=_arr_label(arr),
            channel=channel,
            is_online=is_online,
            description="SIMULATED_TX",
        )
        db.add(tx)
        created.append(tx)

    await db.commit()

    for tx in created:
        await db.refresh(tx)
        await _score_and_maybe_alert(db, tx, threshold=threshold)

    return len(created)


# -----------------------------
# Dashboard summary
# -----------------------------
async def get_dashboard_summary(
    db: AsyncSession,
    *,
    days: int = 30,
    top_n: int = 8,
    simulate: bool = False,
    simulate_n: int = 3,
    alert_threshold: int = 70,
) -> DashboardSummaryOut:
    """
    Construit le payload DashboardSummaryOut (KPI + séries + hotspots).

    Comportement :
    - Si simulate=True : injecte des transactions live avant de calculer les agrégats.
    - Heatmap vivante : arrondissements renvoie toujours 1..20 (même si 0),
      afin que la carte conserve les zones “calme/moyen/chaud”.
    """
    if simulate:
        await _simulate_transactions(db, n=simulate_n, threshold=alert_threshold)

    start_dt, all_dates = _date_range(days)

    # ---------------- KPI ----------------
    tx_total_stmt = select(func.count(Transaction.id))
    tx_window_stmt = select(func.count(Transaction.id)).where(Transaction.occurred_at >= start_dt)

    alerts_total_stmt = select(func.count(Alert.id))
    alerts_open_stmt = select(func.count(Alert.id)).where(Alert.status == "open")
    alerts_critical_stmt = select(func.count(Alert.id)).where(Alert.score_snapshot >= 90)

    avg_score_stmt = (
        select(func.avg(RiskScore.score))
        .join(Transaction, Transaction.id == RiskScore.transaction_id)
        .where(Transaction.occurred_at >= start_dt)
    )

    tx_total = int((await db.execute(tx_total_stmt)).scalar() or 0)
    tx_window = int((await db.execute(tx_window_stmt)).scalar() or 0)

    alerts_total = int((await db.execute(alerts_total_stmt)).scalar() or 0)
    alerts_open = int((await db.execute(alerts_open_stmt)).scalar() or 0)
    alerts_critical = int((await db.execute(alerts_critical_stmt)).scalar() or 0)

    avg_score = (await db.execute(avg_score_stmt)).scalar()
    avg_score_f = float(avg_score) if avg_score is not None else None

    kpis = DashboardKpis(
        transactions_total=tx_total,
        transactions_window=tx_window,
        alerts_total=alerts_total,
        alerts_open=alerts_open,
        alerts_critical=alerts_critical,
        avg_risk_score_window=avg_score_f,
    )

    # ---------------- Série (par jour) ----------------
    per_day_tx_stmt = (
        select(
            func.date(Transaction.occurred_at).label("d"),
            func.count(Transaction.id).label("cnt"),
            func.avg(RiskScore.score).label("avg_score"),
        )
        .select_from(Transaction)
        .outerjoin(RiskScore, RiskScore.transaction_id == Transaction.id)
        .where(Transaction.occurred_at >= start_dt)
        .group_by(func.date(Transaction.occurred_at))
    )
    per_day_tx_rows = (await db.execute(per_day_tx_stmt)).all()
    tx_map: Dict[date, Tuple[int, Optional[float]]] = {}
    for r in per_day_tx_rows:
        tx_map[r.d] = (int(r.cnt), float(r.avg_score) if r.avg_score is not None else None)

    per_day_alert_stmt = (
        select(func.date(Alert.created_at).label("d"), func.count(Alert.id).label("cnt"))
        .where(Alert.created_at >= start_dt)
        .group_by(func.date(Alert.created_at))
    )
    per_day_alert_rows = (await db.execute(per_day_alert_stmt)).all()
    alert_map: Dict[date, int] = {r.d: int(r.cnt) for r in per_day_alert_rows}

    day_points: List[DashboardDayPoint] = []
    for d in all_dates:
        tx_cnt, av = tx_map.get(d, (0, None))
        al_cnt = alert_map.get(d, 0)
        day_points.append(
            DashboardDayPoint(
                date=d.isoformat(),
                transactions=tx_cnt,
                alerts=al_cnt,
                avg_score=av,
            )
        )

    series = DashboardSeries(days=day_points)

    # ---------------- Hotspots / Heatmap ----------------
    arr_stmt = (
        select(
            Transaction.arrondissement.label("key"),
            func.count(Transaction.id).label("cnt"),
            func.avg(RiskScore.score).label("avg_score"),
        )
        .select_from(Transaction)
        .outerjoin(RiskScore, RiskScore.transaction_id == Transaction.id)
        .where(Transaction.occurred_at >= start_dt)
        .group_by(Transaction.arrondissement)
    )
    arr_rows = (await db.execute(arr_stmt)).all()

    # On garantit 1..20 pour garder la carte “calme/moyen/chaud”
    arr_map: Dict[int, Tuple[int, Optional[float]]] = {i: (0, None) for i in range(1, 21)}
    for r in arr_rows:
        n = _parse_arr_num(r.key)
        if not n:
            continue
        arr_map[n] = (int(r.cnt), float(r.avg_score) if r.avg_score is not None else None)

    arr_items: List[HotspotItem] = []
    for n in range(1, 21):
        cnt, av = arr_map[n]
        arr_items.append(HotspotItem(key=_arr_label(n), count=cnt, avg_score=av))

    # Top catégories
    cat_stmt = (
        select(
            Transaction.merchant_category.label("key"),
            func.count(Transaction.id).label("cnt"),
            func.avg(RiskScore.score).label("avg_score"),
        )
        .select_from(Transaction)
        .outerjoin(RiskScore, RiskScore.transaction_id == Transaction.id)
        .where(Transaction.occurred_at >= start_dt)
        .group_by(Transaction.merchant_category)
        .order_by(desc(func.count(Transaction.id)))
        .limit(top_n)
    )
    cat_rows = (await db.execute(cat_stmt)).all()
    cat_items = [
        HotspotItem(
            key=str(r.key),
            count=int(r.cnt),
            avg_score=float(r.avg_score) if r.avg_score is not None else None,
        )
        for r in cat_rows
    ]

    # Top merchants
    mer_stmt = (
        select(
            Transaction.merchant_name.label("key"),
            func.count(Transaction.id).label("cnt"),
            func.avg(RiskScore.score).label("avg_score"),
        )
        .select_from(Transaction)
        .outerjoin(RiskScore, RiskScore.transaction_id == Transaction.id)
        .where(Transaction.occurred_at >= start_dt)
        .group_by(Transaction.merchant_name)
        .order_by(desc(func.count(Transaction.id)))
        .limit(top_n)
    )
    mer_rows = (await db.execute(mer_stmt)).all()
    mer_items = [
        HotspotItem(
            key=str(r.key),
            count=int(r.cnt),
            avg_score=float(r.avg_score) if r.avg_score is not None else None,
        )
        for r in mer_rows
    ]

    hotspots = DashboardHotspots(
        arrondissements=arr_items,
        categories=cat_items,
        merchants=mer_items,
    )

    return DashboardSummaryOut(kpis=kpis, series=series, hotspots=hotspots)
