import asyncio
import json
import logging
import os
import websockets

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
        print(f"AlpacaCryptoStream.start() called")
        print(f"Attempting to connect to: {ALPACA_CRYPTO_WS_URL}")

        async with websockets.connect(ALPACA_CRYPTO_WS_URL) as ws:
            print("WebSocket connected successfully.")
            self._ws = ws
            await self._authenticate()
            await self._subscribe()

            while self._running:
                print("Waiting for message...")
                message = await ws.recv()
                print(f"Raw crypto message received: {message}")

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
            "trades": ["BTC/USD"]
        }
        print(f"Sending subscribe message: {subscribe_message}")
        await self._ws.send(json.dumps(subscribe_message))
