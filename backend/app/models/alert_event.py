from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

"""
Model AlertEvent.

Rôle (fonctionnel) :
- Stocke l’historique (audit trail) des événements liés à une alerte.
- Permet de retracer :
  - les transitions de statut (old_status -> new_status),
  - la nature de l’action (event_type),
  - un message explicatif (reason),
  - l’auteur (actor) si disponible,
  - la traçabilité technique (request_id) pour corréler logs + API.

Relation :
- N événements appartiennent à 1 alerte (Alert 1..N AlertEvent).
- Suppression en cascade : si l’alerte est supprimée, ses events le sont aussi.
"""


class AlertEvent(Base):
    __tablename__ = "alert_events"

    # Identifiant technique (UUID)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # FK vers l’alerte concernée (cascade delete)
    alert_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("alerts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Type d’événement (ex: CREATED, SCORE_UPDATED, STATUS_CHANGED…)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)

    # Transition de statut (optionnelle selon event_type)
    old_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    new_status: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Message humain : motif / commentaire (optionnel)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Acteur de l’action (ex : user/admin/service) — optionnel
    actor: Mapped[str | None] = mapped_column(String(120), nullable=True)

    # Traçabilité technique : request_id HTTP pour corréler API/logs — optionnel
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    # Horodatage de l’événement
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        index=True,
    )

    # Relation ORM : chargement joint pour lecture (historique affichage UI)
    alert = relationship("Alert", back_populates="events", lazy="joined")
