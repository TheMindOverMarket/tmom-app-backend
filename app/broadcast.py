from typing import Set, Optional, Dict
from fastapi import WebSocket
import asyncio
from collections import defaultdict

class MarketStateBroadcaster:
    def __init__(self, name: str = "GENERIC") -> None:
        self.name = name
        self._global_clients: Set[WebSocket] = set()
        self._scoped_clients: Dict[str, Set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()
        self._last_message: Optional[str] = None

    async def connect(self, websocket: WebSocket, user_id: Optional[str] = None) -> None:
        await websocket.accept()
        scope_info = f"user:{user_id}" if user_id else "global"
        print(f"[BROADCAST][{self.name}][CLIENT_CONNECT] New {scope_info} client connected")
        
        async with self._lock:
            if user_id:
                self._scoped_clients[user_id].add(websocket)
            else:
                self._global_clients.add(websocket)
            
            if self._last_message:
                await websocket.send_text(self._last_message)

    async def disconnect(self, websocket: WebSocket, user_id: Optional[str] = None) -> None:
        async with self._lock:
            if user_id and user_id in self._scoped_clients:
                self._scoped_clients[user_id].discard(websocket)
                if not self._scoped_clients[user_id]:
                    del self._scoped_clients[user_id]
            else:
                self._global_clients.discard(websocket)
        print(f"[BROADCAST][{self.name}][CLIENT_DISCONNECTED] Client disconnected from {user_id or 'global'} scope")

    async def broadcast(self, message: str, user_id: Optional[str] = None) -> None:
        """
        Broadcasts a message.
        If user_id is provided, only clients connected with that user_id receive it.
        Otherwise, ALL global clients receive it.
        """
        if not user_id:
            self._last_message = message
        
        async with self._lock:
            # 1. Targeted clients (if user_id provided)
            # 2. Global clients (always receive if no target, or could be configured to receive all)
            targets = list(self._scoped_clients.get(user_id, [])) if user_id else list(self._global_clients)
            
            if targets:
                # print(f"[BROADCAST][{self.name}][EMIT] Broadcasting to {len(targets)} clients in scope {user_id or 'global'}")
                for ws in targets:
                    try:
                        await ws.send_text(message)
                    except Exception:
                        if user_id:
                            self._scoped_clients[user_id].discard(ws)
                        else:
                            self._global_clients.discard(ws)
