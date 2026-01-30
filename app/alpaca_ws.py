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

        if not self._api_key or not self._api_secret:
            raise RuntimeError("Missing Alpaca API credentials")

        self._ws = None
        self._running = True

    async def start(self) -> None:
        # Import inside the function to avoid circular dependency
        from app.main import broadcaster

        print(f"AlpacaCryptoStream.start() called")
        print(f"Attempting to connect to: {ALPACA_CRYPTO_WS_URL}")

        async with websockets.connect(ALPACA_CRYPTO_WS_URL) as ws:
            print("WebSocket connected successfully.")
            self._ws = ws
            await self._authenticate()
            await self._subscribe()

            while self._running:
                message = await ws.recv()
                
                try:
                    data = json.loads(message)
                    if isinstance(data, list):
                        for obj in data:
                            if obj.get("T") == "q":
                                bp = obj.get("bp")
                                ap = obj.get("ap")
                                if bp is not None and ap is not None:
                                    mid_price = (bp + ap) / 2
                                    event = {
                                        "event_type": "market_state",
                                        "symbol": "BTC",
                                        "current_time": datetime.utcnow().isoformat() + "Z",
                                        "price": mid_price
                                    }
                                    event_json = json.dumps(event)
                                    print(event_json)
                                    await broadcaster.broadcast(event_json)
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
        print(f"Sending auth message: {auth_message}")
        await self._ws.send(json.dumps(auth_message))

    async def _subscribe(self) -> None:
        subscribe_message = {
            "action": "subscribe",
            "quotes": ["BTC/USD"]
        }
        print(f"Sending subscribe message: {subscribe_message}")
        await self._ws.send(json.dumps(subscribe_message))
