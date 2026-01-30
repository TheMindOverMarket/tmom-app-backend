import asyncio
import json
import logging
import os
import websockets
from datetime import datetime

logger = logging.getLogger(__name__)

ALPACA_CRYPTO_WS_URL = "wss://stream.data.alpaca.markets/v1beta3/crypto/us"


class AlpacaCryptoStream:
    def __init__(self) -> None:
        self._api_key = os.getenv("ALPACA_API_KEY")
        self._api_secret = os.getenv("ALPACA_API_SECRET")
        self.ws_url = ALPACA_CRYPTO_WS_URL
        self.symbols = ["BTC/USD"]

        if not self._api_key or not self._api_secret:
            raise RuntimeError("Missing Alpaca API credentials")

        self._ws = None
        self._running = True

    async def start(self) -> None:
        # Import inside the function to avoid circular dependency
        from app.main import broadcaster

        print("[ALPACA][START] AlpacaCryptoStream.start() invoked")
        print(f"[ALPACA][CONNECT] Connecting to {self.ws_url}")

        async with websockets.connect(
            self.ws_url,
            ping_interval=20,
            ping_timeout=20,
            open_timeout=10,
            close_timeout=5,
            max_queue=None,
        ) as ws:
            print("[ALPACA][CONNECTED] WebSocket connection established")
            self._ws = ws
            await self._authenticate()
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
                                        "symbol": "BTC", # Keep consistent with prompt instructions or use symbol? 
                                        # Prompt 03b says "symbol": "BTC" explicitly. 
                                        # But here we get "BTC/USD".
                                        # I'll stick to "BTC" as per previous agreement/code if possible, or just use the obj["S"] if I want to be generic
                                        # But let's check previous implementation: `event = { ... "symbol": "BTC", ... }`
                                        # I will keep "BTC" hardcoded for consistency with previous step unless instructed otherwise.
                                        # Wait, 06 instruction says: `print(f"[MARKET_STATE][BUILD] symbol={symbol} ...")`
                                        # So assume I use `symbol` from obj which is likely "BTC/USD".
                                        # But the event schema in 03b said `symbol: "BTC"`.
                                        # I will follow 03b for the event payload, but use the `symbol` variable for the log.
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

    async def stop(self) -> None:
        self._running = False
        if self._ws:
            await self._ws.close()

    async def _authenticate(self) -> None:
        auth_message = {
            "action": "auth",
            "key": self._api_key,
            "secret": self._api_secret
        }
        await self._ws.send(json.dumps(auth_message))
        print("[ALPACA][AUTH_SENT] Auth message sent")

    async def _subscribe(self) -> None:
        subscribe_message = {
            "action": "subscribe",
            "quotes": self.symbols
        }
        await self._ws.send(json.dumps(subscribe_message))
        print(f"[ALPACA][SUBSCRIBE_SENT] Subscribed to quotes: {self.symbols}")
