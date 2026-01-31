import asyncio
import json
import logging
import os
import websockets
from datetime import datetime

logger = logging.getLogger(__name__)

ALPACA_CRYPTO_WS_URL = "wss://stream.data.alpaca.markets/v1beta3/crypto/us"
ALPACA_TRADING_WS_URL = "wss://paper-api.alpaca.markets/stream"


class AlpacaBaseStream:
    def __init__(self, url: str) -> None:
        self._api_key = os.getenv("ALPACA_API_KEY")
        self._api_secret = os.getenv("ALPACA_API_SECRET")
        self.ws_url = url
        self._ws = None
        self._running = True

        if not self._api_key or not self._api_secret:
            raise RuntimeError("Missing Alpaca API credentials")

    async def connect(self):
        return websockets.connect(
            self.ws_url,
            ping_interval=20,
            ping_timeout=20,
            open_timeout=10,
            close_timeout=5,
            max_queue=None,
        )

    async def authenticate(self) -> None:
        auth_message = {
            "action": "auth",
            "key": self._api_key,
            "secret": self._api_secret
        }
        await self._ws.send(json.dumps(auth_message))
        print(f"[{self.__class__.__name__}][AUTH_SENT] Auth message sent")

    async def stop(self) -> None:
        self._running = False
        if self._ws:
            await self._ws.close()


class AlpacaCryptoStream(AlpacaBaseStream):
    def __init__(self) -> None:
        super().__init__(ALPACA_CRYPTO_WS_URL)
        self.symbols = ["BTC/USD"]

    async def start(self) -> None:
        # Import inside the function to avoid circular dependency
        from app.main import broadcaster

        print("[ALPACA][START] AlpacaCryptoStream.start() invoked")
        print(f"[ALPACA][CONNECT] Connecting to {self.ws_url}")

        async with await self.connect() as ws:
            print("[ALPACA][CONNECTED] WebSocket connection established")
            self._ws = ws
            await self.authenticate()
            await self._subscribe()

            while self._running:
                print("[ALPACA][WAITING] Awaiting next message from Alpaca...")
                message = await ws.recv()
                print(f"[ALPACA][RECEIVED_RAW] {message}")
                
                try:
                    print("[ALPACA][PARSE] Parsing incoming message")
                    data = json.loads(message)
                    if isinstance(data, list):
                        for obj in data:
                            if obj.get("T") == "q":
                                bp = obj.get("bp")
                                ap = obj.get("ap")
                                symbol = obj.get("S")
                                print(f"[ALPACA][QUOTE] symbol={symbol} bid={bp} ask={ap}")
                                
                                if bp is not None and ap is not None:
                                    mid_price = (bp + ap) / 2
                                    current_time = datetime.utcnow().isoformat() + "Z"
                                    
                                    print(f"[MARKET_STATE][BUILD] symbol={symbol} price={mid_price} time={current_time}")
                                    
                                    event = {
                                        "event_type": "market_state",
                                        "symbol": "BTC", 
                                        "current_time": current_time,
                                        "price": mid_price
                                    }
                                    
                                    event_json = json.dumps(event)
                                    print("[MARKET_STATE][BROADCAST] Broadcasting market_state event")
                                    await broadcaster.broadcast(event_json)
                            else:
                                print("[ALPACA][IGNORED] Message type not relevant")
                except Exception as e:
                    print(f"Error processing message: {e}")

    async def _subscribe(self) -> None:
        subscribe_message = {
            "action": "subscribe",
            "quotes": self.symbols
        }
        await self._ws.send(json.dumps(subscribe_message))
        print(f"[ALPACA][SUBSCRIBE_SENT] Subscribed to quotes: {self.symbols}")


class AlpacaTradingStream(AlpacaBaseStream):
    def __init__(self) -> None:
        super().__init__(ALPACA_TRADING_WS_URL)

    async def start(self) -> None:
        print("[ALPACA_TRADING][START] AlpacaTradingStream.start() invoked")
        print(f"[ALPACA_TRADING][CONNECT] Connecting to {self.ws_url}")

        try:
            async with await self.connect() as ws:
                print("[ALPACA_TRADING][CONNECTED] WebSocket connection established")
                self._ws = ws
                await self.authenticate()
                await self._subscribe()

                while self._running:
                    try:
                        message = await ws.recv()
                        print(f"[ALPACA][TRADE_UPDATE][RECEIVED] {message}")
                        
                        try:
                            data = json.loads(message)
                            stream = data.get("stream")
                            if stream == "trade_updates":
                                payload = data.get("data", {})
                                event_type = payload.get("event")
                                execution = payload.get("order", {})
                                
                                # Only process relevant event types if needed, but MD says "trade_updates messages"
                                # so we process all logic here.
                                
                                # Extract fields
                                order_id = execution.get("id")
                                symbol = execution.get("symbol")
                                side = execution.get("side")
                                qty = float(execution.get("qty") or 0)
                                filled_qty = float(execution.get("filled_qty") or 0)
                                
                                # Price logic: 'filled_avg_price' is usually present in fills. 
                                # If null, use None.
                                raw_price = execution.get("filled_avg_price")
                                price = float(raw_price) if raw_price else None
                                
                                # Timestamp logic
                                # Alpaca sends timestamps as strings or isoformats usually,
                                # depending on the specific message 'timestamp' or 'created_at'.
                                # For PoC, we try to parse 'timestamp' from the event payload.
                                # MD says "Alpaca-provided timestamp (epoch ms)".
                                # Usually payload['timestamp'] is in nano/micro or ISO.
                                # Let's assume standard ISO or similar and convert, or if it is already numeric.
                                # Actually, `payload` has `timestamp` for the event itself.
                                raw_ts = payload.get("timestamp")
                                ts_alpaca = 0.0
                                if raw_ts:
                                    # Try parsing ISO if string
                                    if isinstance(raw_ts, str):
                                        try:
                                            # Alpaca timestamps are often like "2023-10-27T..."
                                            # We need a robust parser or simple assumption.
                                            # For simplicity, let's use datetime.fromisoformat if valid, 
                                            # removing 'Z' if present.
                                            dt = datetime.fromisoformat(raw_ts.replace('Z', '+00:00'))
                                            ts_alpaca = dt.timestamp() * 1000 # to ms
                                        except ValueError:
                                            pass
                                    elif isinstance(raw_ts, (int, float)):
                                         # If nanoseconds, convert to ms
                                         if raw_ts > 1000000000000000: # heuristic for ns
                                             ts_alpaca = raw_ts / 1000000
                                         else:
                                             ts_alpaca = raw_ts
                                         
                                
                                # Create Normalized Event
                                from app.schemas import UserActivityEvent
                                import uuid
                                import time
                                
                                normalized_event = UserActivityEvent(
                                    activity_id=str(uuid.uuid4()),
                                    alpaca_event_type=event_type or "unknown",
                                    order_id=order_id or "",
                                    symbol=symbol or "",
                                    side=side or "",
                                    qty=qty,
                                    filled_qty=filled_qty,
                                    price=price,
                                    timestamp_alpaca=ts_alpaca,
                                    timestamp_server=time.time() * 1000
                                )
                                
                                print(f"[USER_ACTIVITY][NORMALIZED] {normalized_event.json()}")
                                
                                # Emit downstream (MD 3 requirement)
                                # Using In-Process Broadcast via the existing MarketStateBroadcaster 
                                # (which is actually a general broadcaster despite the name)
                                from app.main import broadcaster
                                await broadcaster.broadcast(normalized_event.json())
                                print(f"[USER_ACTIVITY][EMITTED] {normalized_event.json()}")
                                
                        except json.JSONDecodeError:
                            pass
                        except Exception as e:
                            print(f"[ALPACA_TRADING][ERROR] Normalization failed: {e}")
                            
                    except websockets.ConnectionClosed:
                        print("[ALPACA_TRADING][CLOSED] Connection closed")
                        break

    async def _subscribe(self) -> None:
        subscribe_message = {
            "action": "listen",
            "data": {
                "streams": ["trade_updates"]
            }
        }
        await self._ws.send(json.dumps(subscribe_message))
        print(f"[ALPACA_TRADING][SUBSCRIBE_SENT] Subscribed to trade_updates")
