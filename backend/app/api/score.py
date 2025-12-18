from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional, Any

from fastapi import APIRouter, Depends, HTTPException, Request
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
    """
    Broadcast best-effort (ne casse jamais /score si WS indispo).
    On suppose que app.state.ws_manager existe avec une méthode async broadcast(payload).
    """
    try:
        manager = getattr(request.app.state, "ws_manager", None)
        if manager and hasattr(manager, "broadcast"):
            await manager.broadcast(payload)
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

    # WS: score computed
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
            # si le snapshot change, log event
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
            await db.flush()  # obtenir alert.id

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

        alert_dict = {
            "id": str(alert.id),
            "status": alert.status,
            "score_snapshot": alert.score_snapshot,
            "reason": alert.reason,
            "created_at": alert.created_at,
            "updated_at": alert.updated_at,
        }

        # WS: alert created (ou upsert)
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
