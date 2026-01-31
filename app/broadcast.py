from typing import Set, Optional
from fastapi import WebSocket
import asyncio


class MarketStateBroadcaster:
    def __init__(self, name: str = "GENERIC") -> None:
        self.name = name
        self._clients: Set[WebSocket] = set()
        self._lock = asyncio.Lock()
        self._last_message: Optional[str] = None

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        print(f"[BROADCAST][{self.name}][CLIENT_CONNECT] New WS client connected")
        
        async with self._lock:
            self._clients.add(websocket)
            
            if self._last_message:
                print(f"[BROADCAST][{self.name}][SEND_CACHED] Sending last message to new client")
                await websocket.send_text(self._last_message)
            else:
                print(f"[BROADCAST][{self.name}][NO_CACHE] No message cached yet")

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(websocket)
        print(f"[BROADCAST][{self.name}][CLIENT_DISCONNECTED] Client disconnected")

    async def broadcast(self, message: str) -> None:
        self._last_message = message
        # print(f"[BROADCAST][{self.name}][CACHE] Updated last message") # Reduced noise
        
        async with self._lock:
            if self._clients:
                print(f"[BROADCAST][{self.name}][EMIT] Broadcasting to {len(self._clients)} clients")
            for ws in list(self._clients):
                try:
                    await ws.send_text(message)
                except Exception as e:
                    print(f"[BROADCAST][{self.name}][ERROR] Failed to send to client: {e}")
                    self._clients.discard(ws)
