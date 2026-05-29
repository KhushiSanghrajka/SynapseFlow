import asyncio
from collections import deque
from datetime import datetime, timezone

from fastapi import WebSocket


class LogBus:
    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()
        self._recent_events: deque[dict] = deque(maxlen=500)
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections.add(websocket)
            history = list(self._recent_events)
        for event in history[-60:]:
            await websocket.send_json(event)

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            if websocket in self._connections:
                self._connections.remove(websocket)

    async def publish(self, event: dict) -> None:
        if "timestamp" not in event:
            event["timestamp"] = datetime.now(timezone.utc).isoformat()

        async with self._lock:
            self._recent_events.append(event)
            connections = list(self._connections)

        stale: list[WebSocket] = []
        for ws in connections:
            try:
                await ws.send_json(event)
            except Exception:
                stale.append(ws)

        if stale:
            async with self._lock:
                for ws in stale:
                    self._connections.discard(ws)

