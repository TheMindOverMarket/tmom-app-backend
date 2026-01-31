# 02b_alpaca_crypto_ws_raw.md

> **Purpose**  
> Replace the Alpaca SDK-based websocket with a **raw Alpaca Crypto Market Data WebSocket**
> to reliably receive live BTC/USD data.
>
> This step proves real crypto market data flow end-to-end.
> **No normalization. No downstream streaming.**

---

## Objective

Update the service to:

- Connect directly to Alpaca’s crypto market data WebSocket
- Authenticate explicitly using API key + secret
- Subscribe to BTC/USD crypto quotes
- Log raw incoming messages
- Run as a background asyncio task
- Shut down cleanly

This file **must not** include:
- Event normalization
- Rule engine integration
- Additional abstractions

---

## Alpaca Crypto Market Data WebSocket

**Endpoint (official):**

```
wss://stream.data.alpaca.markets/v1beta3/crypto/us
```

This endpoint:
- Works with **paper or live API keys**
- Is independent of trading environment
- Streams continuous crypto data

---

## Files to Modify / Create

- Create: `app/alpaca_ws.py` (replace existing implementation)
- Modify: `app/lifecycle.py`

Do **not** modify:
- `app/main.py`
- Project structure
- Other files

---

## Implementation Instructions

### 1. Replace `app/alpaca_ws.py`

Overwrite the file with the following implementation:

```python
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
        logger.info("Connecting to Alpaca Crypto Market Data WebSocket")

        async with websockets.connect(ALPACA_CRYPTO_WS_URL) as ws:
            self._ws = ws
            await self._authenticate()
            await self._subscribe()

            while self._running:
                message = await ws.recv()
                logger.info(f"Raw crypto message: {message}")

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

    async def _subscribe(self) -> None:
        subscribe_message = {
            "action": "subscribe",
            "quotes": ["BTC/USD"]
        }
        await self._ws.send(json.dumps(subscribe_message))
```

Notes:
- Authentication and subscription are **explicit**
- Messages are logged verbatim
- No parsing or schema logic yet

---

### 2. Modify `app/lifecycle.py`

Update lifecycle hooks to use the new raw websocket client.

```python
import asyncio
from app.alpaca_ws import AlpacaCryptoStream

_stream_task: asyncio.Task | None = None
_stream: AlpacaCryptoStream | None = None


async def on_startup() -> None:
    global _stream_task, _stream

    _stream = AlpacaCryptoStream()
    _stream_task = asyncio.create_task(_stream.start())


async def on_shutdown() -> None:
    global _stream_task, _stream

    if _stream:
        await _stream.stop()

    if _stream_task:
        _stream_task.cancel()
        try:
            await _stream_task
        except asyncio.CancelledError:
            pass
```

---

## Acceptance Criteria

After executing this file:

- Service starts with `uvicorn app.main:app --reload`
- BTC/USD crypto quote messages are logged within seconds
- No websocket 404 errors
- No SDK usage remains
- Service shuts down cleanly

---

## Troubleshooting Notes

- Ensure `.env` contains valid Alpaca API credentials
- Quotes should arrive frequently; silence indicates auth or subscribe failure
- Logging level may need to be INFO or lower

---

## End of File 02b
