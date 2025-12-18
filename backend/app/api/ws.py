from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(tags=["realtime"])


@router.websocket("/ws/alerts")
async def ws_alerts(ws: WebSocket):
    manager = getattr(ws.app.state, "ws_manager", None)
    if manager is None:
        await ws.close(code=1011)
        return

    await manager.connect(ws)

    await ws.send_json({"type": "WS_CONNECTED", "ts": datetime.now(timezone.utc).isoformat()})

    try:
        while True:
            # On attend un message client (optionnel, ex: PING)
            msg = await ws.receive_text()
            if msg.strip().upper() == "PING":
                await ws.send_json({"type": "PONG", "ts": datetime.now(timezone.utc).isoformat()})
    except WebSocketDisconnect:
        await manager.disconnect(ws)
    except Exception:
        await manager.disconnect(ws)
