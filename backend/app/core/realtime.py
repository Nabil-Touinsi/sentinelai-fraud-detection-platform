from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Set

from fastapi import WebSocket

"""
Core Realtime (WebSocket Manager).

Rôle (fonctionnel) :
- Centralise la gestion des connexions WebSocket actives.
- Fournit des primitives simples utilisées par l’API :
  - connect / disconnect
  - send_json (1 client)
  - broadcast_json (tous les clients)
  - broadcast (alias compat)

Notes :
- “Best-effort” : les erreurs d’envoi ne doivent pas casser le flux applicatif.
- Purge automatique : si une connexion est morte, elle est retirée du pool.
- Verrou asyncio : protège l’accès concurrent au set de connexions.
"""

logger = logging.getLogger("realtime")


class ConnectionManager:
    """
    Gestionnaire WebSocket minimal.

    Responsabilités :
    - Gérer le cycle de vie des connexions (accept, add/remove).
    - Diffuser des événements JSON à une ou plusieurs connexions.
    - Maintenir un pool propre (purge des connexions mortes).
    """

    def __init__(self) -> None:
        self._connections: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    def count(self) -> int:
        """Nombre de connexions WS actives."""
        return len(self._connections)

    async def connect(self, ws: WebSocket) -> None:
        """Accepte et enregistre une nouvelle connexion."""
        await ws.accept()
        async with self._lock:
            self._connections.add(ws)
        logger.info("WS connected (%s total)", self.count())

    async def disconnect(self, ws: WebSocket) -> None:
        """Retire une connexion (si présente)."""
        async with self._lock:
            self._connections.discard(ws)
        logger.info("WS disconnected (%s total)", self.count())

    async def send_json(self, ws: WebSocket, payload: Dict[str, Any]) -> None:
        """Envoi vers une seule connexion (best-effort)."""
        try:
            await ws.send_json(payload)
        except Exception:
            # Si erreur, on sort silencieusement (la route WS gère souvent la fermeture)
            pass

    async def broadcast_json(self, payload: Dict[str, Any]) -> None:
        """Diffuse un payload à toutes les connexions, puis purge celles qui sont mortes."""
        async with self._lock:
            conns = list(self._connections)

        if not conns:
            return

        dead: list[WebSocket] = []
        for ws in conns:
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)

        if dead:
            async with self._lock:
                for ws in dead:
                    self._connections.discard(ws)
            logger.info("WS purged %s dead conns (%s remaining)", len(dead), self.count())

    async def broadcast(self, payload: Dict[str, Any]) -> None:
        """Alias compat : certains endroits peuvent appeler broadcast(payload)."""
        await self.broadcast_json(payload)

    async def close_all(self) -> None:
        """Optionnel : ferme toutes les connexions WS (best-effort)."""
        async with self._lock:
            conns = list(self._connections)
            self._connections.clear()

        for ws in conns:
            try:
                await ws.close()
            except Exception:
                pass
