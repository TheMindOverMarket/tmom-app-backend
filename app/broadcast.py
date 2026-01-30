from typing import Set
from fastapi import WebSocket
import asyncio


class MarketStateBroadcaster:
    def __init__(self) -> None:
        self._clients: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._clients.add(websocket)

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(websocket)

    async def broadcast(self, message: str) -> None:
        async with self._lock:
            for ws in list(self._clients):
                try:
                    await ws.send_text(message)
                except Exception:
                    self._clients.discard(ws)
