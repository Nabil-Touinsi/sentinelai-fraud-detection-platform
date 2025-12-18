from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, ConfigDict, Field


class AlertStatus(str, Enum):
    A_TRAITER = "A_TRAITER"
    EN_ENQUETE = "EN_ENQUETE"
    CLOTURE = "CLOTURE"


class AlertPatch(BaseModel):
    status: AlertStatus
    comment: Optional[str] = Field(default=None, max_length=2000)

    model_config = ConfigDict(extra="forbid")


class AlertEventOut(BaseModel):
    id: uuid.UUID
    alert_id: uuid.UUID
    event_type: str
    old_status: Optional[str] = None
    new_status: Optional[str] = None
    message: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AlertOut(BaseModel):
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
    page: int
    page_size: int
    total: int


class AlertListItem(BaseModel):
    alert: AlertOut
    transaction: Dict[str, Any]
    risk_score: Optional[Dict[str, Any]] = None


class AlertListResponse(BaseModel):
    data: List[AlertListItem]
    meta: PageMeta
