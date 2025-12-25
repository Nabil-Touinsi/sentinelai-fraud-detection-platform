from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, ConfigDict, Field

"""
Schemas Alerts (Pydantic).

Rôle (fonctionnel) :
- Définit le contrat HTTP autour des alertes (requests / responses).
- Valide et sérialise :
  - la mise à jour partielle d’une alerte (patch statut + commentaire),
  - la représentation d’une alerte,
  - la représentation des événements d’historique (audit),
  - les réponses paginées pour la liste.

Notes :
- Ces schémas sont distincts des modèles ORM (app.models.*).
- ConfigDict(from_attributes=True) permet de construire un schéma depuis un objet ORM.
"""


class AlertStatus(str, Enum):
    """Statuts métier possibles d’une alerte (workflow)."""
    A_TRAITER = "A_TRAITER"
    EN_ENQUETE = "EN_ENQUETE"
    CLOTURE = "CLOTURE"


class AlertPatch(BaseModel):
    """Payload de mise à jour d’alerte (changement de statut + commentaire optionnel)."""
    status: AlertStatus
    comment: Optional[str] = Field(default=None, max_length=2000)

    # Refuse les champs inattendus (API contract strict)
    model_config = ConfigDict(extra="forbid")


class AlertEventOut(BaseModel):
    """Sortie API pour un événement d’historique d’alerte (audit trail)."""
    id: uuid.UUID
    alert_id: uuid.UUID
    event_type: str
    old_status: Optional[str] = None
    new_status: Optional[str] = None
    message: Optional[str] = None

    # Traçabilité (optionnelle) : acteur + request_id
    actor: Optional[str] = None
    request_id: Optional[str] = None

    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AlertOut(BaseModel):
    """Sortie API pour une alerte (snapshot score + statut + métadonnées)."""
    id: uuid.UUID
    transaction_id: uuid.UUID
    risk_score_id: uuid.UUID
    score_snapshot: int
    status: str
    reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PageMeta(BaseModel):
    """Métadonnées de pagination (page, taille, total)."""
    page: int
    page_size: int
    total: int


class AlertListItem(BaseModel):
    """
    Élément de liste d’alertes.

    Composition :
- alert : l’alerte (schéma stable)
- transaction : infos transaction (dict sérialisé)
- risk_score : infos score (optionnel)
    """
    alert: AlertOut
    transaction: Dict[str, Any]
    risk_score: Optional[Dict[str, Any]] = None


class AlertListResponse(BaseModel):
    """Réponse paginée pour la liste des alertes."""
    data: List[AlertListItem]
    meta: PageMeta
