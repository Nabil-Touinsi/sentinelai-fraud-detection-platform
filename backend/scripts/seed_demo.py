# backend/scripts/seed_demo.py
from __future__ import annotations

import argparse
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import sessionmaker

# Permet de lancer le script depuis backend/ sans souci d'import
BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.core.settings import settings
from app.models.alert import Alert
from app.models.alert_event import AlertEvent
from app.models.risk_score import RiskScore
from app.models.transaction import Transaction



# ---- Données réalistes (FR/Paris-friendly) ----
CATEGORIES = [
    "grocery", "restaurant", "fuel", "transport", "ecommerce",
    "electronics", "pharmacy", "fashion", "hotel", "subscription",
]

MERCHANTS = {
    "grocery": ["Carrefour", "Monoprix", "Franprix", "Auchan", "Lidl", "Intermarché"],
    "restaurant": ["McDonald's", "KFC", "Starbucks", "Boulangerie Ducoin", "Sushi Shop", "Pizza Roma"],
    "fuel": ["TotalEnergies", "Esso", "BP", "E.Leclerc Station", "Shell"],
    "transport": ["Uber", "Bolt", "SNCF Connect", "RATP", "G7 Taxi"],
    "ecommerce": ["Amazon", "Cdiscount", "Vinted", "Leboncoin", "AliExpress"],
    "electronics": ["Fnac", "Darty", "Boulanger", "Apple Store Online"],
    "pharmacy": ["Pharmacie Centrale", "Pharmacie de la Gare", "Doctipharma"],
    "fashion": ["Zara", "H&M", "Uniqlo", "Nike.com", "Adidas"],
    "hotel": ["Booking.com", "Airbnb", "Accor", "B&B Hotels"],
    "subscription": ["Netflix", "Spotify", "Deezer", "Amazon Prime", "Adobe"],
}

# Arrondissements (Paris 1..20) + quelques communes (pour faire “vrai”)
ARRONDISSEMENTS = [f"Paris {i}e" for i in range(1, 21)] + [
    "Montreuil", "Saint-Denis", "Aubervilliers", "Pantin", "Ivry-sur-Seine", "Boulogne-Billancourt"
]


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def weighted_amount(category: str) -> float:
    # Montants plausibles par catégorie
    if category == "grocery":
        return round(max(5, random.gauss(45, 25)), 2)
    if category == "restaurant":
        return round(max(5, random.gauss(25, 18)), 2)
    if category == "fuel":
        return round(max(10, random.gauss(70, 35)), 2)
    if category == "transport":
        return round(max(3, random.gauss(18, 12)), 2)
    if category == "pharmacy":
        return round(max(3, random.gauss(22, 15)), 2)
    if category == "subscription":
        return round(max(3, random.gauss(12, 6)), 2)
    if category == "hotel":
        return round(max(30, random.gauss(140, 90)), 2)
    if category in ("ecommerce", "electronics", "fashion"):
        return round(max(5, random.gauss(85, 70)), 2)
    return round(max(5, random.gauss(40, 30)), 2)


def compute_risk_score(amount: float, category: str, is_online: bool, occurred_at: datetime) -> int:
    # Heuristique simple + bruit : suffisant pour démo
    base = 10

    # Montant
    if amount > 300:
        base += 35
    elif amount > 150:
        base += 20
    elif amount > 80:
        base += 10

    # Catégorie “plus risquée” (ecommerce/electronics)
    if category in ("electronics", "ecommerce"):
        base += 12
    if category == "hotel":
        base += 8

    # Online
    if is_online:
        base += 10

    # Heures “bizarres” (nuit)
    hour = occurred_at.hour
    if hour <= 5:
        base += 12
    elif hour >= 23:
        base += 8

    # Bruit aléatoire
    base += random.randint(-8, 18)

    return max(0, min(100, int(base)))


def seed(reset: bool, n: int, days: int, alert_threshold: int) -> None:
    engine = create_engine(settings.DATABASE_URL_SYNC, future=True)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    with SessionLocal() as db:
        if reset:
            # ordre inverse des FK
            db.execute(delete(AlertEvent))
            db.execute(delete(Alert))
            db.execute(delete(RiskScore))
            db.execute(delete(Transaction))
            db.commit()
            print("✅ Reset done (all demo data deleted).")

        start = now_utc() - timedelta(days=days)

        alerts_count = 0
        events_count = 0

        for i in range(n):
            category = random.choice(CATEGORIES)
            merchant = random.choice(MERCHANTS[category])
            amount = weighted_amount(category)

            # Occurred date aléatoire sur la fenêtre
            occurred_at = start + timedelta(
                seconds=random.randint(0, int((now_utc() - start).total_seconds()))
            )

            # Online : très probable pour ecommerce/subscription, moins sinon
            if category in ("ecommerce", "subscription", "electronics"):
                is_online = random.random() < 0.85
            elif category in ("transport", "hotel", "fashion"):
                is_online = random.random() < 0.55
            else:
                is_online = random.random() < 0.20

            tx = Transaction(
                id=uuid4(),
                occurred_at=occurred_at,
                created_at=now_utc(),
                amount=amount,
                currency="EUR",
                merchant_name=merchant,
                merchant_category=category,
                arrondissement=random.choice(ARRONDISSEMENTS),
                channel="card",
                is_online=is_online,
                description=None,
            )
            db.add(tx)
            db.flush()  # récupère tx.id

            score = compute_risk_score(amount, category, is_online, occurred_at)

            rs = RiskScore(
                id=uuid4(),
                transaction_id=tx.id,
                score=score,
                model_version="v1",
                features={
                    "amount": amount,
                    "category": category,
                    "is_online": is_online,
                    "hour": occurred_at.hour,
                },
                created_at=now_utc(),
            )
            db.add(rs)
            db.flush()

            if score >= alert_threshold:
                alerts_count += 1

                # statut initial
                status = "open"
                reason = "Score élevé détecté"

                alert = Alert(
                    id=uuid4(),
                    transaction_id=tx.id,
                    risk_score_id=rs.id,
                    score_snapshot=score,
                    status=status,
                    reason=reason,
                    created_at=now_utc(),
                    updated_at=now_utc(),
                )
                db.add(alert)
                db.flush()

                # event: created
                db.add(
                    AlertEvent(
                        id=uuid4(),
                        alert_id=alert.id,
                        event_type="created",
                        old_status=None,
                        new_status="open",
                        message="Alerte créée automatiquement",
                        created_at=now_utc(),
                    )
                )
                events_count += 1

                # parfois une évolution de statut (pour démo)
                roll = random.random()
                if roll < 0.35:
                    new_status = "triaged"
                elif roll < 0.55:
                    new_status = "closed"
                else:
                    new_status = None

                if new_status:
                    alert.status = new_status
                    alert.updated_at = now_utc()
                    db.add(
                        AlertEvent(
                            id=uuid4(),
                            alert_id=alert.id,
                            event_type="status_change",
                            old_status="open",
                            new_status=new_status,
                            message=f"Statut mis à jour vers '{new_status}'",
                            created_at=now_utc(),
                        )
                    )
                    events_count += 1

            # commit par batch (plus rapide)
            if (i + 1) % 200 == 0:
                db.commit()
                print(f"… {i+1}/{n} transactions insérées")

        db.commit()

        # petit résumé
        total_tx = db.execute(select(Transaction).count()).scalar() if hasattr(select(Transaction), "count") else None
        print("✅ Seed terminé.")
        print(f"   - Transactions ajoutées: {n}")
        print(f"   - Alerts créées (score >= {alert_threshold}): {alerts_count}")
        print(f"   - Alert events créés: {events_count}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="Supprime les données demo avant de reseed")
    parser.add_argument("--n", type=int, default=800, help="Nombre de transactions à générer")
    parser.add_argument("--days", type=int, default=90, help="Fenêtre de dates (derniers N jours)")
    parser.add_argument("--threshold", type=int, default=settings.ALERT_THRESHOLD, help="Seuil score pour créer une alerte")
    parser.add_argument("--seed", type=int, default=42, help="Seed RNG pour reproductibilité")
    args = parser.parse_args()

    random.seed(args.seed)
    seed(reset=args.reset, n=args.n, days=args.days, alert_threshold=args.threshold)


if __name__ == "__main__":
    main()
