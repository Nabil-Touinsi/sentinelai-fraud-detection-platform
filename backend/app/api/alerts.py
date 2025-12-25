from __future__ import annotations

import uuid
import logging
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import asc, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import DemoAuthDep
from app.db.session import get_db
from app.models.alert import Alert
from app.models.alert_event import AlertEvent
from app.models.risk_score import RiskScore
from app.models.transaction import Transaction
from app.schemas.alerts import (
    AlertEventOut,
    AlertListResponse,
    AlertPatch,
    PageMeta,
)

"""
API Alertes.

Rôle (fonctionnel) :
- Lister les alertes (avec transaction + score associés) et pagination/tri.
- Lister l’historique (events) d’une alerte.
- Mettre à jour le statut d’une alerte (protégé en mode démo) et tracer l’action :
  - en base via alert_events
  - en logs via request_id/actor
  - en temps réel via WebSocket (si activé)
"""

router = APIRouter(prefix="/alerts", tags=["alerts"])
log = logging.getLogger("app.alerts")


def _priority_order():
    # Tri “priorité” : score desc, puis date desc
    return [desc(Alert.score_snapshot), desc(Alert.created_at)]


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


async def _safe_broadcast(request: Request, payload: dict) -> None:
    """Envoie un event WS sans faire échouer l’endpoint si le WS n’est pas disponible."""
    try:
        manager = getattr(request.app.state, "ws_manager", None)
        if manager is None:
            return
        await manager.broadcast_json(payload)
    except Exception:
        return


@router.get("", response_model=AlertListResponse)
async def list_alerts(
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    status: str | None = None,
    min_score: int | None = Query(None, ge=0, le=100),
    sort_by: str = Query("priority", pattern="^(priority|date)$"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
):
    stmt = (
        select(Alert, Transaction, RiskScore)
        .join(Transaction, Transaction.id == Alert.transaction_id)
        .join(RiskScore, RiskScore.id == Alert.risk_score_id)
    )

    if status:
        stmt = stmt.where(Alert.status == status)
    if min_score is not None:
        stmt = stmt.where(Alert.score_snapshot >= min_score)

    # Tri
    if sort_by == "priority":
        stmt = stmt.order_by(*_priority_order())
    else:
        stmt = stmt.order_by(desc(Alert.created_at) if order == "desc" else asc(Alert.created_at))

    # Total pour la pagination
    count_stmt = select(func.count()).select_from(Alert)
    if status:
        count_stmt = count_stmt.where(Alert.status == status)
    if min_score is not None:
        count_stmt = count_stmt.where(Alert.score_snapshot >= min_score)

    total = (await db.execute(count_stmt)).scalar_one()

    # Pagination
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(stmt)).all()

    data = []
    for alert, tx, rs in rows:
        data.append(
            {
                "alert": alert,
                "transaction": {
                    "id": str(tx.id),
                    "occurred_at": tx.occurred_at,
                    "amount": str(tx.amount),
                    "currency": tx.currency,
                    "merchant_name": tx.merchant_name,
                    "merchant_category": tx.merchant_category,
                    "arrondissement": tx.arrondissement,
                    "channel": tx.channel,
                    "is_online": tx.is_online,
                },
                "risk_score": {
                    "id": str(rs.id),
                    "score": rs.score,
                    "model_version": rs.model_version,
                    "created_at": rs.created_at,
                }
                if rs
                else None,
            }
        )

    return {"data": data, "meta": PageMeta(page=page, page_size=page_size, total=total)}


@router.get("/{alert_id}/events", response_model=List[AlertEventOut])
async def list_alert_events(
    alert_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    alert = (await db.execute(select(Alert).where(Alert.id == alert_id))).scalars().first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    events = (
        await db.execute(
            select(AlertEvent)
            .where(AlertEvent.alert_id == alert_id)
            .order_by(asc(AlertEvent.created_at))
        )
    ).scalars().all()

    return events


@router.patch("/{alert_id}", dependencies=[DemoAuthDep])
async def patch_alert(
    alert_id: uuid.UUID,
    payload: AlertPatch,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    # Endpoint protégé (mode démo)
    alert = (await db.execute(select(Alert).where(Alert.id == alert_id))).scalars().first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    # Identifiant de requête pour la traçabilité (logs + alert_events)
    rid = getattr(request.state, "request_id", None) or str(uuid.uuid4())

    # Auteur de l’action (header X-Actor côté front)
    actor = request.headers.get("X-Actor") or "demo_admin"

    # Commentaire obligatoire si clôture
    new_status = payload.status.value
    if new_status == "CLOTURE" and not (payload.comment and payload.comment.strip()):
        raise HTTPException(status_code=422, detail="comment is required when closing an alert")

    old_status = alert.status
    alert.status = new_status
    alert.updated_at = datetime.now(timezone.utc)

    db.add(
        AlertEvent(
            alert_id=alert.id,
            event_type="STATUS_CHANGE",
            old_status=old_status,
            new_status=alert.status,
            message=payload.comment,
            actor=actor,
            request_id=rid,
            created_at=datetime.now(timezone.utc),
        )
    )

    await db.commit()
    await db.refresh(alert)

    alert_payload = {
        "id": str(alert.id),
        "status": alert.status,
        "updated_at": _iso(alert.updated_at),
    }

    # Log structuré (corrélation via request_id)
    log.info(
        "alert_status_change",
        extra={
            "request_id": rid,
            "actor": actor,
            "alert_id": str(alert.id),
            "old_status": old_status,
            "new_status": alert.status,
        },
    )

    # Event temps réel (si WS actif)
    await _safe_broadcast(
        request,
        {
            "type": "ALERT_STATUS_CHANGED",
            "ts": datetime.now(timezone.utc).isoformat(),
            "data": {
                "alert": alert_payload,
                "old_status": old_status,
                "comment": payload.comment,
                "actor": actor,
                "request_id": rid,
            },
        },
    )

    return alert_payload
