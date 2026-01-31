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
                    except websockets.ConnectionClosed:
                        print("[ALPACA_TRADING][CLOSED] Connection closed")
                        break
        except Exception as e:
             print(f"[ALPACA_TRADING][ERROR] Connection failed: {e}")

    async def _subscribe(self) -> None:
        subscribe_message = {
            "action": "listen",
            "data": {
                "streams": ["trade_updates"]
            }
        }
        await self._ws.send(json.dumps(subscribe_message))
        print(f"[ALPACA_TRADING][SUBSCRIBE_SENT] Subscribed to trade_updates")
