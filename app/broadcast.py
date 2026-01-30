from typing import Set, Optional
from fastapi import WebSocket
import asyncio


class MarketStateBroadcaster:
    def __init__(self) -> None:
        self._clients: Set[WebSocket] = set()
        self._lock = asyncio.Lock()
        self._last_message: Optional[str] = None

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        print("[BROADCAST][CLIENT_CONNECT] New WS client connected")
        
        async with self._lock:
            self._clients.add(websocket)
            
            if self._last_message:
                print("[BROADCAST][SEND_CACHED] Sending last market_state to new client")
                await websocket.send_text(self._last_message)
            else:
                print("[BROADCAST][NO_CACHE] No market_state cached yet")

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(websocket)

    async def broadcast(self, message: str) -> None:
        self._last_message = message
        print("[BROADCAST][CACHE] Updated last market_state")
        
        async with self._lock:
            for ws in list(self._clients):
                try:
                    await ws.send_text(message)
                except Exception:
                    self._clients.discard(ws)
