# 03_market_state_event_schema.md

> **Purpose**  
> Introduce a canonical `MarketStateEvent` schema and normalize raw Alpaca
> crypto websocket messages into this schema.
>
> This step transforms **raw websocket messages → structured market state events**.
> **No downstream streaming yet.**

---

## Objective

Extend the service to:

- Define a canonical `MarketStateEvent`
- Parse raw Alpaca crypto websocket messages
- Extract market state from BTC/USD trade messages
- Emit normalized `MarketStateEvent` objects (via logging / print)

This file **must not** include:
- Rule engine integration
- WebSocket server endpoints
- Persistence
- Complex error handling

---

## Canonical MarketStateEvent Schema

The normalized event must have the following shape:

```json
{
  "event_type": "market_state",
  "symbol": "BTC/USD",
  "timestamp": "2026-01-30T14:32:18.123Z",
  "price": 43125.42,
  "metrics": {}
}
```

Notes:
- `timestamp` must be ISO 8601 UTC
- `metrics` is extensible but empty for now
- Event is emitted **only for trade messages**

---

## Files to Modify / Create

- Create: `app/schemas.py`
- Modify: `app/alpaca_ws.py`

Do **not** modify:
- `app/lifecycle.py`
- `app/main.py`
- Project structure

---

## Implementation Instructions

### 1. Create `app/schemas.py`

Define a Pydantic model for `MarketStateEvent`.

```python
from pydantic import BaseModel
from typing import Dict


class MarketStateEvent(BaseModel):
    event_type: str = "market_state"
    symbol: str
    timestamp: str
    price: float
    metrics: Dict[str, float]
```

Notes:
- Keep `timestamp` as a string (already ISO formatted)
- Do not add validation logic yet

---

### 2. Modify `app/alpaca_ws.py`

Update the websocket client to:

- Parse incoming messages as JSON
- Ignore non-trade messages
- Normalize trade messages into `MarketStateEvent`
- Emit the normalized event via `print()`

#### Required logic

Inside the receive loop:

1. Parse the message using `json.loads`
2. Alpaca messages arrive as **lists** of objects
3. For each object:
   - If `T == "t"` (trade message):
     - Extract:
       - `S` → symbol
       - `p` → price
       - `t` → timestamp
     - Create a `MarketStateEvent`
     - Print the serialized event (`.json()`)

#### Example transformation (conceptual)

```python
if obj["T"] == "t":
    event = MarketStateEvent(
        symbol=obj["S"],
        price=obj["p"],
        timestamp=obj["t"],
        metrics={}
    )
    print(event.json())
```

Notes:
- Do not emit events for control messages
- Do not enrich metrics yet
- Leave raw message logging in place if useful

---

## Acceptance Criteria

After executing this file:

- Service starts normally
- When BTC/USD trades occur:
  - Raw websocket messages are received
  - Normalized `MarketStateEvent` JSON is printed
- No schema violations
- No changes to lifecycle or startup logic

---

## End of File 03
