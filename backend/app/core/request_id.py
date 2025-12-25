from __future__ import annotations

import uuid
from contextvars import ContextVar

"""
Core Request ID.

Rôle (fonctionnel) :
- Gère un identifiant de requête (request_id) stocké dans un ContextVar.
- Permet de corréler logs, erreurs et événements pour une même requête.
- Le request_id peut être :
  - fourni par un header entrant (ex : X-Request-Id),
  - ou généré automatiquement si absent.

Notes :
- ContextVar est adapté aux contextes async (FastAPI) : chaque requête garde son propre request_id.
- Ce module est utilisé par :
  - logging (injection dans les logs),
  - middleware / handlers d’erreurs (propagation du request_id),
  - éventuellement le temps réel (corrélation d’events).
"""

_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)


def set_request_id(rid: str | None) -> None:
    """Force la valeur du request_id pour le contexte courant."""
    _request_id.set(rid)


def get_request_id() -> str | None:
    """Retourne le request_id du contexte courant (ou None)."""
    return _request_id.get()


def ensure_request_id(incoming: str | None = None) -> str:
    """
    Garantit un request_id pour le contexte courant.

    - Si un request_id entrant est fourni, il est nettoyé et réutilisé.
    - Sinon, on génère un UUID.
    """
    rid = (incoming or "").strip() or str(uuid.uuid4())
    set_request_id(rid)
    return rid
