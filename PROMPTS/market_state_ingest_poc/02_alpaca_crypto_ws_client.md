# 02_alpaca_crypto_ws_client.md

> **Purpose**  
> Connect the service to real Alpaca crypto market data via WebSocket  
> and log raw BTC/USD messages.  
>  
> This step proves end-to-end connectivity only.  
> **No normalization. No downstream streaming.**

---

## Objective

Extend the existing FastAPI service to:

- Connect to Alpaca Crypto Market Data WebSocket
- Subscribe to BTC/USD trades
- Run the websocket client as a background asyncio task
- Log raw incoming messages to stdout
- Shut down cleanly

This file **must not** include:
- Event normalization
- Rule engine integration
- Custom schemas beyond placeholders

---

## Prerequisites

You must have Alpaca API credentials available as environment variables:

```
ALPACA_API_KEY
ALPACA_API_SECRET
```

This file assumes **paper trading / crypto data access is enabled**.

---

## Files to Modify / Create

- Modify: `requirements.txt`
- Create: `app/alpaca_ws.py`
- Modify: `app/lifecycle.py`

Do **not** modify `app/main.py` yet.

---

## Implementation Instructions

### 1. Update `requirements.txt`

Add the official Alpaca SDK:

```
alpaca-trade-api
```

Do not remove existing dependencies.

---

### 2. Create `app/alpaca_ws.py`

Create a module responsible only for managing the Alpaca WebSocket connection.

```python
import asyncio
import logging
from alpaca_trade_api.stream import Stream

logger = logging.getLogger(__name__)


class AlpacaCryptoStream:
    def __init__(self, api_key: str, api_secret: str) -> None:
        self._stream = Stream(
            api_key,
            api_secret,
            base_url="https://paper-api.alpaca.markets",
            data_feed="crypto"
        )

    async def start(self) -> None:
        @self._stream.on_crypto_trades("BTC/USD")
        async def on_trade(trade):
            logger.info(f"Raw trade event: {trade}")

        await self._stream._run_forever()

    async def stop(self) -> None:
        await self._stream.stop()
```

Notes:
- This intentionally logs raw trade objects
- No parsing or transformation
- Uses Alpaca’s async stream client

---

### 3. Modify `app/lifecycle.py`

Attach the websocket client as a background task.

```python
import asyncio
import os
from app.alpaca_ws import AlpacaCryptoStream

_stream_task: asyncio.Task | None = None


async def on_startup() -> None:
    global _stream_task

    api_key = os.getenv("ALPACA_API_KEY")
    api_secret = os.getenv("ALPACA_API_SECRET")

    if not api_key or not api_secret:
        raise RuntimeError("Missing Alpaca API credentials")

    stream = AlpacaCryptoStream(api_key, api_secret)
    _stream_task = asyncio.create_task(stream.start())


async def on_shutdown() -> None:
    global _stream_task

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
- On startup, BTC/USD trade events are logged
- No schema transformations occur
- Service shuts down without hanging
- No changes to `main.py`

---

## Troubleshooting Notes

- If no data arrives:
  - Confirm crypto data access in Alpaca dashboard
  - Confirm API keys are correct
- Logs may be verbose — this is expected for this step

---

## End of File 02
