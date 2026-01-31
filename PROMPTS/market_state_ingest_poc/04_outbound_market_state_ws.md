# 04_outbound_market_state_ws.md

> **Purpose**  
> Expose the normalized `market_state` stream to downstream consumers
> (e.g., the rule engine) via a WebSocket endpoint.
>
> This step turns the aggregator into a **producer** of market_state events.

---

## Objective

Extend the service to:

- Maintain the existing Alpaca ingestion + normalization pipeline
- Add an outbound WebSocket endpoint for downstream systems
- Stream `market_state` events to all connected clients in real time
- Keep the implementation minimal and stateless

This file **must not** include:
- Rule evaluation logic
- Persistence or replay
- Authentication / authorization
- Complex fan-out or backpressure handling

---

## Canonical Outbound Event

The outbound payload must be **exactly** the canonical market state event:

```json
{
  "event_type": "market_state",
  "symbol": "BTC",
  "current_time": "2026-01-30T21:13:49.087421Z",
  "price": 43125.42
}
```

No additional fields. No envelopes.

---

## Files to Modify / Create

- Modify: `app/alpaca_ws.py`
- Modify: `app/main.py`
- Create: `app/broadcast.py`

Do **not** modify:
- `app/lifecycle.py`
- Project structure
- Existing schema definitions

---

## Design Overview (Simple & Intentional)

- A single **in-memory broadcaster**
- All connected WebSocket clients receive the same stream
- No buffering guarantees (best-effort delivery)
- Suitable for Wizard-of-Oz + early rule engine integration

---

## Implementation Instructions

### 1. Create `app/broadcast.py`

Implement a minimal broadcaster to manage downstream WebSocket clients.

```python
from typing import Set
from fastapi import WebSocket
import asyncio


class MarketStateBroadcaster:
    def __init__(self) -> None:
        self._clients: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._clients.add(websocket)

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(websocket)

    async def broadcast(self, message: str) -> None:
        async with self._lock:
            for ws in list(self._clients):
                try:
                    await ws.send_text(message)
                except Exception:
                    self._clients.discard(ws)
```

---

### 2. Modify `app/main.py`

Add a WebSocket endpoint that downstream systems can connect to.

```python
from fastapi import WebSocket, WebSocketDisconnect
from app.broadcast import MarketStateBroadcaster

broadcaster = MarketStateBroadcaster()


@app.websocket("/ws/market-state")
async def market_state_ws(websocket: WebSocket):
    await broadcaster.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await broadcaster.disconnect(websocket)
```

Notes:
- The server does not expect messages from clients
- The receive loop keeps the connection alive

---

### 3. Modify `app/alpaca_ws.py`

When a `market_state` event is emitted:

- Serialize it to JSON
- Send it to the broadcaster **in addition to printing it**

#### Required change (conceptual)

```python
await broadcaster.broadcast(event_json)
```

Implementation notes:
- Import the broadcaster instance from `app.main`
- Do not introduce circular dependencies (import inside function if needed)
- Broadcasting must be **non-blocking** relative to ingestion

---

## Acceptance Criteria

After executing this file:

- Service starts normally
- Visiting `/ws/market-state` establishes a WebSocket connection
- Connected clients receive live `market_state` events
- Multiple clients can connect simultaneously
- No crashes when clients disconnect

---

## Manual Test (Suggested)

1. Start the service
2. Connect via `wscat` or browser devtools:
   ```
   wscat -c ws://localhost:8000/ws/market-state
   ```
3. Observe streaming `market_state` JSON payloads

---

## End of File 04
