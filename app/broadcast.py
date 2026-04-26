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
        self._last_message_time: float = 0

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
            
            # Freshness Check: Only send the last message if it's < 60s old
            now = asyncio.get_event_loop().time()
            if self._last_message and (now - self._last_message_time < 60.0):
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

    async def broadcast(self, message: str, user_id: Optional[str | list[str]] = None, session_id: Optional[str] = None) -> None:
        """
        Broadcasts a message with hierarchical targeting:
        - If session_id is provided, sends to session-specific clients.
        - If user_id (or a list) is provided, sends to user-wide clients.
        - Always sends to global clients for generic monitoring/debugging.
        """
        if not user_id and not session_id:
            self._last_message = message
            self._last_message_time = asyncio.get_event_loop().time()
        
        async with self._lock:
            # Collect all unique targets across the hierarchy
            targets = set(self._global_clients)
            
            if user_id:
                if isinstance(user_id, list):
                    for uid in user_id:
                        targets.update(self._user_clients.get(uid, []))
                else:
                    targets.update(self._user_clients.get(user_id, []))
            
            if session_id:
                targets.update(self._session_clients.get(session_id, []))
            
            if targets:
                # We use a list to avoid issues if targets set is modified during iteration
                for ws in list(targets):
                    try:
                        await ws.send_text(message)
                    except Exception:
                        # Clean up stale connections
                        if session_id:
                            self._session_clients[session_id].discard(ws)
                        if user_id:
                            self._user_clients[user_id].discard(ws)
                        self._global_clients.discard(ws)
