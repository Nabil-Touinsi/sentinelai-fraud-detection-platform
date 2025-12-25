from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

"""
Schemas Transactions (Pydantic).

Rôle (fonctionnel) :
- Définit le contrat HTTP des transactions (création, listing, détail).
- Fournit une validation stricte côté API pour sécuriser les entrées :
  - refuse les champs inconnus (extra="forbid")
  - valide montants / formats / longueurs
  - parse robuste des dates ISO (compat PowerShell / front)
  - empêche occurred_at dans le futur (tolérance 2 minutes)

Notes :
- Ces schémas sont distincts des modèles ORM (app.models.*).
- from_attributes=True permet de sérialiser directement depuis des objets SQLAlchemy.
"""


def _parse_iso_datetime(value: str) -> datetime:
    """
    Parse robuste de datetime ISO pour compat clients variés.

    Accepte :
    - "2025-12-21T18:48:00Z"
    - "2025-12-21T18:48:00.4600072Z" (7 digits -> tronqué à 6)
    - "2025-12-21T18:48:00.460007+00:00"

    Comportement :
    - "Z" est converti en "+00:00" pour datetime.fromisoformat
    - la fraction de secondes est tronquée à 6 digits si nécessaire
    - si tzinfo absent : UTC par défaut
    """
    s = value.strip()

    # "Z" -> "+00:00" pour fromisoformat
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"

    # Tronquer la fraction de secondes à 6 digits si besoin
    # Exemple: ...T18:48:00.4600072+00:00 -> ...T18:48:00.460007+00:00
    if "." in s:
        head, rest = s.split(".", 1)
        # rest = "4600072+00:00" ou "460007+00:00" ou "460007"
        frac = rest
        tz = ""
        if "+" in rest:
            frac, tz = rest.split("+", 1)
            tz = "+" + tz
        elif "-" in rest[1:]:
            # timezone négatif possible, éviter le '-' de la date
            frac, tz = rest.split("-", 1)
            tz = "-" + tz

        frac_digits = "".join(ch for ch in frac if ch.isdigit())
        if len(frac_digits) > 6:
            frac_digits = frac_digits[:6]
        # Si fraction vide -> on enlève le point
        if frac_digits:
            s = f"{head}.{frac_digits}{tz}"
        else:
            s = f"{head}{tz}"

    dt = datetime.fromisoformat(s)

    # Si pas de tzinfo, considérer UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return dt


class TransactionCreate(BaseModel):
    """
    Payload de création de transaction.

    Objectifs :
    - Validation stricte (API contract) : extra="forbid"
    - Normalisation : amount -> Decimal, currency -> upper, channel -> lower, strip strings
    - Robustesse date : parse ISO string + pas dans le futur (tolérance 2 minutes)
    """
    model_config = ConfigDict(extra="forbid")

    occurred_at: datetime

    # Bornes “raisonnables” pour une démo
    amount: Decimal = Field(..., gt=Decimal("0"), le=Decimal("1000000"))

    # ISO 4217 3 lettres (EUR, USD...) + normalisation en MAJ
    currency: str = Field(default="EUR", min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")

    merchant_name: str = Field(..., min_length=1, max_length=255)
    merchant_category: str = Field(..., min_length=1, max_length=100)

    arrondissement: Optional[str] = Field(default=None, max_length=50)

    # Reste un string (compat) mais contraint (ex: "card", "transfer", "mobile_pay"...)
    channel: str = Field(default="card", min_length=2, max_length=30, pattern=r"^[a-z_]+$")

    is_online: bool = False
    description: Optional[str] = Field(default=None, max_length=2000)

    @field_validator("amount", mode="before")
    @classmethod
    def _amount_to_decimal(cls, v: Any) -> Any:
        """Normalise amount vers Decimal (les clients envoient souvent int/float)."""
        if isinstance(v, Decimal):
            return v
        if isinstance(v, int):
            return Decimal(v)
        if isinstance(v, float):
            return Decimal(str(v))
        if isinstance(v, str):
            s = v.strip()
            if not s:
                return v
            try:
                return Decimal(s)
            except InvalidOperation:
                return v
        return v

    @field_validator("occurred_at", mode="before")
    @classmethod
    def _occurred_at_parse(cls, v: Any) -> Any:
        """Autorise occurred_at au format string ISO (PowerShell / front)."""
        if isinstance(v, str):
            return _parse_iso_datetime(v)
        return v

    @field_validator("occurred_at")
    @classmethod
    def _occurred_at_not_future(cls, v: datetime) -> datetime:
        """Empêche occurred_at dans le futur (tolérance 2 minutes)."""
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)

        now = datetime.now(timezone.utc)
        if v > (now + timedelta(minutes=2)):
            raise ValueError("occurred_at ne peut pas être dans le futur")
        return v

    @field_validator("currency", mode="before")
    @classmethod
    def _currency_upper(cls, v: Any) -> Any:
        """Normalise currency en MAJ."""
        if isinstance(v, str):
            return v.strip().upper()
        return v

    @field_validator("channel", mode="before")
    @classmethod
    def _channel_lower(cls, v: Any) -> Any:
        """Normalise channel en minuscule."""
        if isinstance(v, str):
            return v.strip().lower()
        return v

    @field_validator("merchant_name", "merchant_category", mode="before")
    @classmethod
    def _strip_strings(cls, v: Any) -> Any:
        """Strip des champs texte (évite espaces en entrée)."""
        if isinstance(v, str):
            return v.strip()
        return v


class RiskScoreOut(BaseModel):
    """Sortie API pour un RiskScore (score + version + features + date)."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    score: int
    model_version: str
    features: Optional[dict[str, Any]] = None
    created_at: datetime


class AlertOut(BaseModel):
    """Sortie API minimaliste pour l’alerte associée à une transaction."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: str
    score_snapshot: int
    reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class TransactionOut(BaseModel):
    """Sortie API pour une transaction (données de base + contexte)."""
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
    """Élément de liste : transaction + score + alerte (optionnels)."""
    transaction: TransactionOut
    risk_score: Optional[RiskScoreOut] = None
    alert: Optional[AlertOut] = None


class PageMeta(BaseModel):
    """Métadonnées de pagination (page, taille, total)."""
    page: int
    page_size: int
    total: int


class TransactionListResponse(BaseModel):
    """Réponse paginée pour /transactions."""
    data: list[TransactionListItem]
    meta: PageMeta


class TransactionDetailResponse(BaseModel):
    """Réponse détaillée pour /transactions/{id}."""
    transaction: TransactionOut
    risk_score: Optional[RiskScoreOut] = None
    alert: Optional[AlertOut] = None
