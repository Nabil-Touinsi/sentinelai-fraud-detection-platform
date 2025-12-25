from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

"""
API Realtime (WebSocket).

Rôle (fonctionnel) :
- Fournit un canal WebSocket pour pousser des événements “temps réel” vers le front.
- Principal usage : événements liés aux alertes (création / mise à jour).
- Le WS est best-effort : si le manager WS n’est pas initialisé, la connexion est refusée.

Notes :
- Le client peut envoyer des messages (optionnel). Exemple : "PING" → réponse "PONG".
- Les événements “métier” sont envoyés ailleurs (ex: /score) via ws_manager.broadcast_*.
"""

router = APIRouter(tags=["realtime"])


@router.websocket("/ws/alerts")
async def ws_alerts(ws: WebSocket):
    # Récupère le WS manager initialisé au démarrage (app.state.ws_manager)
    manager = getattr(ws.app.state, "ws_manager", None)
    if manager is None:
        # Erreur serveur : WS non disponible / non initialisé
        await ws.close(code=1011)
        return

    # Enregistre la connexion côté manager
    await manager.connect(ws)

    # Ack de connexion (utile côté UI pour confirmer la connexion)
    await ws.send_json({"type": "WS_CONNECTED", "ts": datetime.now(timezone.utc).isoformat()})

    try:
        while True:
            # Attente d’un message client (optionnel, ex : PING)
            msg = await ws.receive_text()
            if msg.strip().upper() == "PING":
                await ws.send_json({"type": "PONG", "ts": datetime.now(timezone.utc).isoformat()})
    except WebSocketDisconnect:
        # Déconnexion “normale” (fermeture client)
        await manager.disconnect(ws)
    except Exception:
        # Sécurité : on nettoie la connexion même en cas d’erreur inattendue
        await manager.disconnect(ws)
