from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.errors import AppHTTPException
from app.db.session import get_db
from app.models.alert import Alert
from app.models.risk_score import RiskScore
from app.models.transaction import Transaction
from app.schemas.transactions import (
    AlertOut,
    PageMeta,
    RiskScoreOut,
    TransactionCreate,
    TransactionDetailResponse,
    TransactionListItem,
    TransactionListResponse,
    TransactionOut,
)

router = APIRouter()


def _risk_level(score: int) -> str:
    # utile plus tard (UI) — optionnel, mais pratique
    if score >= 70:
        return "HIGH"
    if score >= 40:
        return "MEDIUM"
    return "LOW"


@router.post("/transactions", response_model=TransactionOut)
async def create_transaction(payload: TransactionCreate, db: AsyncSession = Depends(get_db)):
    tx = Transaction(
        occurred_at=payload.occurred_at,
        created_at=datetime.utcnow(),
        amount=payload.amount,
        currency=payload.currency,
        merchant_name=payload.merchant_name,
        merchant_category=payload.merchant_category,
        arrondissement=payload.arrondissement,
        channel=payload.channel,
        is_online=payload.is_online,
        description=payload.description,
    )

    db.add(tx)
    await db.commit()
    await db.refresh(tx)
    return TransactionOut.model_validate(tx)


@router.get("/transactions", response_model=TransactionListResponse)
async def list_transactions(
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),

    # filtres (étape 3)
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    arrondissement: Optional[str] = None,
    category: Optional[str] = None,

    min_score: Optional[int] = Query(None, ge=0, le=100),
    max_score: Optional[int] = Query(None, ge=0, le=100),
    alert_status: Optional[str] = None,
):
    # --- "latest alert" par transaction (évite doublons si plusieurs alertes) ---
    latest_alert_subq = (
        select(
            Alert.transaction_id.label("tx_id"),
            func.max(Alert.created_at).label("max_created"),
        )
        .group_by(Alert.transaction_id)
        .subquery()
    )
    LatestAlert = aliased(Alert)

    stmt = (
        select(Transaction, RiskScore, LatestAlert)
        .outerjoin(RiskScore, RiskScore.transaction_id == Transaction.id)
        .outerjoin(latest_alert_subq, latest_alert_subq.c.tx_id == Transaction.id)
        .outerjoin(
            LatestAlert,
            (LatestAlert.transaction_id == Transaction.id) & (LatestAlert.created_at == latest_alert_subq.c.max_created),
        )
    )

    # filtres sur transactions
    if date_from:
        stmt = stmt.where(Transaction.occurred_at >= date_from)
    if date_to:
        stmt = stmt.where(Transaction.occurred_at <= date_to)
    if arrondissement:
        stmt = stmt.where(Transaction.arrondissement == arrondissement)
    if category:
        stmt = stmt.where(Transaction.merchant_category == category)

    # filtres sur risk_score / alert
    if min_score is not None:
        stmt = stmt.where(RiskScore.score >= min_score)
    if max_score is not None:
        stmt = stmt.where(RiskScore.score <= max_score)
    if alert_status:
        stmt = stmt.where(LatestAlert.status == alert_status)

    # tri + pagination
    stmt = stmt.order_by(Transaction.occurred_at.desc())
    offset = (page - 1) * page_size
    stmt = stmt.offset(offset).limit(page_size)

    # total (count distinct sur tx)
    count_stmt = (
        select(func.count(func.distinct(Transaction.id)))
        .select_from(Transaction)
        .outerjoin(RiskScore, RiskScore.transaction_id == Transaction.id)
        .outerjoin(latest_alert_subq, latest_alert_subq.c.tx_id == Transaction.id)
        .outerjoin(
            LatestAlert,
            (LatestAlert.transaction_id == Transaction.id) & (LatestAlert.created_at == latest_alert_subq.c.max_created),
        )
    )

    if date_from:
        count_stmt = count_stmt.where(Transaction.occurred_at >= date_from)
    if date_to:
        count_stmt = count_stmt.where(Transaction.occurred_at <= date_to)
    if arrondissement:
        count_stmt = count_stmt.where(Transaction.arrondissement == arrondissement)
    if category:
        count_stmt = count_stmt.where(Transaction.merchant_category == category)
    if min_score is not None:
        count_stmt = count_stmt.where(RiskScore.score >= min_score)
    if max_score is not None:
        count_stmt = count_stmt.where(RiskScore.score <= max_score)
    if alert_status:
        count_stmt = count_stmt.where(LatestAlert.status == alert_status)

    total = (await db.execute(count_stmt)).scalar_one()

    rows = (await db.execute(stmt)).all()

    items: list[TransactionListItem] = []
    for tx, rs, al in rows:
        items.append(
            TransactionListItem(
                transaction=TransactionOut.model_validate(tx),
                risk_score=RiskScoreOut.model_validate(rs) if rs else None,
                alert=AlertOut.model_validate(al) if al else None,
            )
        )

    return TransactionListResponse(
        data=items,
        meta=PageMeta(page=page, page_size=page_size, total=total),
    )


@router.get("/transactions/{transaction_id}", response_model=TransactionDetailResponse)
async def get_transaction_detail(transaction_id: UUID, db: AsyncSession = Depends(get_db)):
    stmt = (
        select(Transaction, RiskScore, Alert)
        .outerjoin(RiskScore, RiskScore.transaction_id == Transaction.id)
        .outerjoin(Alert, Alert.transaction_id == Transaction.id)
        .where(Transaction.id == transaction_id)
    )

    row = (await db.execute(stmt)).first()
    if not row:
        raise AppHTTPException(404, "NOT_FOUND", "Transaction introuvable")

    tx, rs, al = row

    return TransactionDetailResponse(
        transaction=TransactionOut.model_validate(tx),
        risk_score=RiskScoreOut.model_validate(rs) if rs else None,
        alert=AlertOut.model_validate(al) if al else None,
    )
