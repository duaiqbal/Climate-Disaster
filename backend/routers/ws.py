"""
backend/routers/ws.py
======================
WebSocket endpoint for real-time alert streaming to Flutter clients.

Connect:  ws://localhost:8002/ws/alerts
Protocol: JSON text frames

Server → Client message types:
  connected   — sent on handshake  {type, message, server_ts, client_id}
  new_alert   — new/updated alert  {type, server_ts, alert: {...}}
  monitor_done — monitor finished  {type, new_alerts, server_ts, message}
  ping        — heartbeat          {type, server_ts}

Client → Server:
  Any text frame is echoed back as a pong (keeps connection alive).
"""

import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from core.ws_manager import ws_manager

router = APIRouter(tags=["WebSocket"])
logger = logging.getLogger(__name__)


@router.websocket("/ws/alerts")
async def ws_alerts(websocket: WebSocket) -> None:
    """
    Real-time alert stream.
    Flutter app connects once; server pushes every new alert instantly.
    Falls back gracefully if client disconnects.
    """
    cid = await ws_manager.connect(websocket)
    try:
        while True:
            # Keep connection alive — echo any client ping back as pong
            data = await websocket.receive_text()
            await websocket.send_text(f'{{"type":"pong","echo":{data!r}}}')
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.warning("[WS] Client #%d error: %s", cid, exc)
    finally:
        ws_manager.disconnect(cid)
