from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import settings
from app.db.session import get_db
from app.models.transaction import Transaction
from app.models.risk_score import RiskScore
from app.models.alert import Alert
from app.models.alert_event import AlertEvent
from app.services.scoring_service import ScoringService

"""
API Scoring.

Rôle (fonctionnel) :
- Calcule un score de risque pour une transaction existante.
- Persiste le score (risk_scores).
- Si le score dépasse le seuil, crée ou met à jour une alerte (alerts) + son historique (alert_events).
- Publie des events temps réel via WebSocket (si disponible).
"""

router = APIRouter(tags=["score"])


class ScoreRequest(BaseModel):
    transaction_id: uuid.UUID
    model_config = ConfigDict(extra="forbid")


class ScoreResponse(BaseModel):
    transaction_id: uuid.UUID
    score: int
    risk_level: str
    factors: list[str]
    threshold: int
    alert: Optional[dict] = None


async def _ws_broadcast(request: Request, payload: dict[str, Any]) -> None:
    """Envoie un event WS sans faire échouer l’endpoint si le WS n’est pas disponible."""
    try:
        manager = getattr(request.app.state, "ws_manager", None)
        if not manager:
            return

        # Rend le payload compatible JSON (UUID/datetime/Decimal…)
        safe_payload = jsonable_encoder(payload)

        if hasattr(manager, "broadcast_json"):
            await manager.broadcast_json(safe_payload)
            return

        # Fallback si le manager change
        if hasattr(manager, "broadcast"):
            await manager.broadcast(safe_payload)
    except Exception:
        pass


@router.post("/score", response_model=ScoreResponse)
async def score_one(
    payload: ScoreRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    tx = (
        (await db.execute(select(Transaction).where(Transaction.id == payload.transaction_id)))
        .scalars()
        .first()
    )
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")

    svc = ScoringService()
    res = await svc.score_and_persist(db, tx)

    # Recharge le RiskScore (utile pour l’alerte)
    rs = (
        (await db.execute(select(RiskScore).where(RiskScore.transaction_id == tx.id)))
        .scalars()
        .first()
    )

    # Event WS : score calculé
    await _ws_broadcast(
        request,
        {
            "type": "SCORE_COMPUTED",
            "ts": datetime.now(timezone.utc).isoformat(),
            "data": {
                "transaction_id": str(tx.id),
                "score": int(res.score),
                "risk_level": str(res.risk_level),
                "threshold": int(settings.ALERT_THRESHOLD),
            },
        },
    )

    alert_dict = None
    if rs and int(res.score) >= int(settings.ALERT_THRESHOLD):
        existing_alert = (
            (await db.execute(select(Alert).where(Alert.risk_score_id == rs.id)))
            .scalars()
            .first()
        )

        if existing_alert:
            # Mise à jour du snapshot si le score change
            if existing_alert.score_snapshot != int(res.score):
                old = existing_alert.score_snapshot
                existing_alert.score_snapshot = int(res.score)
                existing_alert.updated_at = datetime.utcnow()

                db.add(
                    AlertEvent(
                        alert_id=existing_alert.id,
                        event_type="SCORE_UPDATED",
                        old_status=existing_alert.status,
                        new_status=existing_alert.status,
                        message=f"score_snapshot: {old} -> {int(res.score)}",
                        created_at=datetime.utcnow(),
                    )
                )
            alert = existing_alert
        else:
            # Création d’une nouvelle alerte
            alert = Alert(
                transaction_id=tx.id,
                risk_score_id=rs.id,
                score_snapshot=int(res.score),
                status="A_TRAITER",
                reason="Score élevé détecté",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.add(alert)
            await db.flush()  # récupère alert.id

            db.add(
                AlertEvent(
                    alert_id=alert.id,
                    event_type="CREATED",
                    old_status=None,
                    new_status="A_TRAITER",
                    message=f"Alerte créée automatiquement (score >= {settings.ALERT_THRESHOLD})",
                    created_at=datetime.utcnow(),
                )
            )

        await db.commit()
        await db.refresh(alert)

        alert_dict = jsonable_encoder(
            {
                "id": str(alert.id),
                "status": alert.status,
                "score_snapshot": int(alert.score_snapshot),
                "reason": alert.reason,
                "created_at": alert.created_at,
                "updated_at": alert.updated_at,
            }
        )

        # Event WS : alerte créée / mise à jour
        await _ws_broadcast(
            request,
            {
                "type": "ALERT_CREATED",
                "ts": datetime.now(timezone.utc).isoformat(),
                "data": {
                    "alert": alert_dict,
                    "transaction_id": str(tx.id),
                },
            },
        )

    return ScoreResponse(
        transaction_id=tx.id,
        score=int(res.score),
        risk_level=str(res.risk_level),
        factors=list(res.factors),
        threshold=int(settings.ALERT_THRESHOLD),
        alert=alert_dict,
    )
