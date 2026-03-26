from typing import Set, Optional, Dict
from fastapi import WebSocket
import asyncio
from collections import defaultdict

class MarketStateBroadcaster:
    def __init__(self, name: str = "GENERIC") -> None:
        self.name = name
        self._global_clients: Set[WebSocket] = set()
        self._user_clients: Dict[str, Set[WebSocket]] = defaultdict(set)
        self._session_clients: Dict[str, Set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()
        self._last_message: Optional[str] = None

    async def connect(self, websocket: WebSocket, user_id: Optional[str] = None, session_id: Optional[str] = None) -> None:
        await websocket.accept()
        scope_info = f"session:{session_id}" if session_id else (f"user:{user_id}" if user_id else "global")
        print(f"[BROADCAST][{self.name}][CLIENT_CONNECT] New {scope_info} client connected")
        
        async with self._lock:
            if session_id:
                self._session_clients[session_id].add(websocket)
            elif user_id:
                self._user_clients[user_id].add(websocket)
            else:
                self._global_clients.add(websocket)
            
            if self._last_message:
                await websocket.send_text(self._last_message)

    async def disconnect(self, websocket: WebSocket, user_id: Optional[str] = None, session_id: Optional[str] = None) -> None:
        async with self._lock:
            if session_id and session_id in self._session_clients:
                self._session_clients[session_id].discard(websocket)
                if not self._session_clients[session_id]:
                    del self._session_clients[session_id]
            elif user_id and user_id in self._user_clients:
                self._user_clients[user_id].discard(websocket)
                if not self._user_clients[user_id]:
                    del self._user_clients[user_id]
            else:
                self._global_clients.discard(websocket)
        print(f"[BROADCAST][{self.name}][CLIENT_DISCONNECTED] Client disc. from {session_id or user_id or 'global'} scope")

    async def broadcast(self, message: str, user_id: Optional[str] = None, session_id: Optional[str] = None) -> None:
        """
        Broadcasts a message with hierarchical fallback:
        - If session_id is provided, sends to session clients.
        - If user_id is provided, sends to user clients.
        - Otherwise, sends to global clients.
        """
        if not user_id and not session_id:
            self._last_message = message
        
        async with self._lock:
            targets = []
            if session_id:
                targets = list(self._session_clients.get(session_id, []))
            elif user_id:
                targets = list(self._user_clients.get(user_id, []))
            else:
                targets = list(self._global_clients)
            
            if targets:
                for ws in targets:
                    try:
                        await ws.send_text(message)
                    except Exception:
                        if session_id:
                            self._session_clients[session_id].discard(ws)
                        elif user_id:
                            self._user_clients[user_id].discard(ws)
                        else:
                            self._global_clients.discard(ws)
