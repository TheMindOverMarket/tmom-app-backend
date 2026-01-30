# 03b_market_state_from_quotes.md

> **Purpose**  
> Emit canonical `market_state` events derived from **crypto quote updates**  
> instead of trades, ensuring a continuous and reliable market state stream.
>
> This step replaces trade-based emission with quote-based emission.

---

## Objective

Update the service to:

- Subscribe to **BTC/USD crypto quotes**
- Derive market state from quote updates
- Emit a simplified canonical `market_state` payload
- Use ingestion-time UTC as the canonical timestamp

This file **must not** include:
- Rule engine integration
- WebSocket server endpoints
- Persistence
- Additional metrics beyond price

---

## Canonical Market State Payload (LOCKED)

The emitted payload must have **exactly** this shape:

```json
{
  "event_type": "market_state",
  "symbol": "BTC",
  "current_time": "2026-01-30T14:32:18.123Z",
  "price": 43125.42
}
```

### Semantics
- `symbol`: base asset only (`BTC`)
- `current_time`: ISO 8601 UTC timestamp at ingestion time
- `price`: mid-price derived from quote (`(bid + ask) / 2`)

---

## Files to Modify

- Modify: `app/alpaca_ws.py`

Do **not** modify:
- `app/lifecycle.py`
- `app/main.py`
- Project structure
- Dependencies

---

## Implementation Instructions

### 1. Update Subscription

In the websocket subscribe message:
- Replace `trades` with `quotes`
- Subscribe to `"BTC/USD"`

---

### 2. Update Message Handling Logic

Inside the websocket receive loop:

1. Parse incoming messages using `json.loads`
2. Alpaca messages arrive as **lists** of objects
3. For each object:
   - If `T == "q"` (quote message):
     - Extract:
       - `bp` → bid price
       - `ap` → ask price
     - Compute:
       - `price = (bp + ap) / 2`
     - Generate `current_time` using `datetime.utcnow().isoformat() + "Z"`
     - Emit the canonical market state payload via `print()`

---

### 3. Example Emission Logic (Conceptual)

```python
if obj["T"] == "q":
    mid_price = (obj["bp"] + obj["ap"]) / 2
    event = {
        "event_type": "market_state",
        "symbol": "BTC",
        "current_time": datetime.utcnow().isoformat() + "Z",
        "price": mid_price
    }
    print(json.dumps(event))
```

Notes:
- Do NOT emit events for non-quote messages
- Do NOT include extra fields
- Do NOT reuse the quote timestamp — use ingestion time

---

## Acceptance Criteria

After executing this file:

- Service starts normally
- BTC/USD quote messages are received
- A `market_state` JSON payload is printed **frequently**
- Payload matches the canonical schema exactly
- No errors or crashes

---

## End of File 03b
