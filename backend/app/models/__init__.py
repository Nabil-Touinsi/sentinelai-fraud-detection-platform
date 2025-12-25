"""
app.models

Package ORM (SQLAlchemy) : définition des entités persistées en base.

Rôle (fonctionnel) :
- Centralise les modèles principaux de l’application (Transaction, RiskScore, Alert, AlertEvent).
- Permet des imports plus simples depuis app.models (ex: from app.models import Transaction).
- Expose explicitement l’API publique du package via __all__ (évite imports implicites).
"""

from app.models.transaction import Transaction
from app.models.risk_score import RiskScore
from app.models.alert import Alert
from app.models.alert_event import AlertEvent

__all__ = ["Transaction", "RiskScore", "Alert", "AlertEvent"]
