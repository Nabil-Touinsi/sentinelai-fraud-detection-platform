from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Set

from fastapi import WebSocket

logger = logging.getLogger("realtime")


class ConnectionManager:
    """
    Manager WebSocket simple:
    - connect / disconnect
    - broadcast_json(payload)
    - broadcast(payload) alias (compat)
    """

    def __init__(self) -> None:
        self._connections: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    def count(self) -> int:
        return len(self._connections)

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._connections.add(ws)
        logger.info("WS connected (%s total)", self.count())

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            self._connections.discard(ws)
        logger.info("WS disconnected (%s total)", self.count())

    async def send_json(self, ws: WebSocket, payload: Dict[str, Any]) -> None:
        """Envoi à une seule connexion (best-effort)."""
        try:
            await ws.send_json(payload)
        except Exception:
            # si erreur, on sort silencieusement (la route WS gère souvent la fermeture)
            pass

    async def broadcast_json(self, payload: Dict[str, Any]) -> None:
        """Broadcast à toutes les connexions, et purge celles qui sont mortes."""
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
        """
        Alias compat si ailleurs dans le code on appelle broadcast(payload)
        """
        await self.broadcast_json(payload)

    async def close_all(self) -> None:
        """Optionnel : fermer toutes les connexions."""
        async with self._lock:
            conns = list(self._connections)
            self._connections.clear()

        for ws in conns:
            try:
                await ws.close()
            except Exception:
                pass
