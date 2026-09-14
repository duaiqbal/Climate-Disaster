"""
backend/core/ws_manager.py
===========================
WebSocket connection manager for real-time alert broadcasting.

All connected Flutter clients receive a JSON push the moment
a new alert is created — no polling needed.

Usage:
    from core.ws_manager import ws_manager

    # In WebSocket endpoint:
    await ws_manager.connect(websocket)

    # In alert creation / scheduler:
    await ws_manager.broadcast_alert(alert_dict)
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class AlertBroadcastManager:
    """Thread-safe in-process WebSocket connection registry."""

    def __init__(self) -> None:
        # active WebSocket connections: {connection_id: WebSocket}
        self._connections: dict[int, WebSocket] = {}
        self._id_counter: int = 0

    # ── Connection lifecycle ───────────────────────────────────────────────────

    async def connect(self, ws: WebSocket) -> int:
        """Accept a new WebSocket connection, return its assigned ID."""
        await ws.accept()
        self._id_counter += 1
        cid = self._id_counter
        self._connections[cid] = ws
        logger.info("[WS] Client #%d connected — total=%d", cid, len(self._connections))

        # Send welcome + current timestamp so client can detect latency
        await self._send_one(ws, {
            "type":      "connected",
            "message":   "ChitralSafe real-time alerts active",
            "server_ts": datetime.now(timezone.utc).isoformat(),
            "client_id": cid,
        })
        return cid

    def disconnect(self, cid: int) -> None:
        """Remove a connection (call from finally block)."""
        self._connections.pop(cid, None)
        logger.info("[WS] Client #%d disconnected — total=%d", cid, len(self._connections))

    # ── Broadcasting ───────────────────────────────────────────────────────────

    async def broadcast_alert(self, alert: dict[str, Any]) -> None:
        """Push a new/updated alert to ALL connected clients."""
        if not self._connections:
            return

        payload = {
            "type":      "new_alert",
            "server_ts": datetime.now(timezone.utc).isoformat(),
            "alert":     alert,
        }
        await self._broadcast(payload)
        logger.info("[WS] Broadcast alert '%s' to %d clients",
                    alert.get("title", "?"), len(self._connections))

    async def broadcast_ping(self) -> None:
        """Send a heartbeat ping to all clients so they stay alive."""
        await self._broadcast({
            "type":      "ping",
            "server_ts": datetime.now(timezone.utc).isoformat(),
        })

    async def broadcast_monitor_done(self, new_count: int) -> None:
        """Notify clients that the monitor finished and N new alerts were found."""
        await self._broadcast({
            "type":      "monitor_done",
            "new_alerts": new_count,
            "server_ts": datetime.now(timezone.utc).isoformat(),
            "message":   f"Monitor run complete — {new_count} new alert(s) fetched",
        })

    # ── Internal helpers ───────────────────────────────────────────────────────

    async def _broadcast(self, payload: dict[str, Any]) -> None:
        """Send payload to all clients; remove any that fail."""
        dead: list[int] = []
        text = json.dumps(payload, default=str)
        for cid, ws in list(self._connections.items()):
            try:
                await ws.send_text(text)
            except Exception:
                dead.append(cid)
        for cid in dead:
            self.disconnect(cid)

    @staticmethod
    async def _send_one(ws: WebSocket, payload: dict[str, Any]) -> None:
        try:
            await ws.send_text(json.dumps(payload, default=str))
        except Exception:
            pass

    @property
    def client_count(self) -> int:
        return len(self._connections)


# ── Singleton ─────────────────────────────────────────────────────────────────
ws_manager = AlertBroadcastManager()
