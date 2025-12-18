from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TransactionCreate(BaseModel):
    occurred_at: datetime
    amount: Decimal = Field(..., gt=0)
    currency: str = Field(default="EUR", min_length=3, max_length=3)

    merchant_name: str = Field(..., min_length=1, max_length=255)
    merchant_category: str = Field(..., min_length=1, max_length=100)

    arrondissement: Optional[str] = Field(default=None, max_length=50)
    channel: str = Field(default="card", max_length=30)
    is_online: bool = False
    description: Optional[str] = None


class RiskScoreOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    score: int
    model_version: str
    features: Optional[dict[str, Any]] = None
    created_at: datetime


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: str
    score_snapshot: int
    reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    occurred_at: datetime
    created_at: datetime

    amount: Decimal
    currency: str

    merchant_name: str
    merchant_category: str

    arrondissement: Optional[str] = None
    channel: str
    is_online: bool
    description: Optional[str] = None


class TransactionListItem(BaseModel):
    transaction: TransactionOut
    risk_score: Optional[RiskScoreOut] = None
    alert: Optional[AlertOut] = None


class PageMeta(BaseModel):
    page: int
    page_size: int
    total: int


class TransactionListResponse(BaseModel):
    data: list[TransactionListItem]
    meta: PageMeta


class TransactionDetailResponse(BaseModel):
    transaction: TransactionOut
    risk_score: Optional[RiskScoreOut] = None
    alert: Optional[AlertOut] = None
