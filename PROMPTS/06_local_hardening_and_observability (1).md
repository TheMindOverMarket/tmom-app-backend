# 06_local_hardening_and_observability.md

## Goal

Before deploying to production, we want **full local certainty** that:

1. Alpaca crypto data is actually flowing (not just connected)
2. We know *exactly* where things break if data is missing
3. The outbound WebSocket only depends on verified upstream input
4. Logs are explicit, traceable, and timestamped

This step intentionally adds **verbose observability** and **local-only validation**.

---

## Scope (Strict)

This step will:

- Switch Alpaca WS feed to `crypto/global`
- Add last-value caching for market_state
- Add structured print-based observability (not logging framework refactors)
- Add a root `/` endpoint
- Validate end-to-end **locally**

This step will NOT:

- Deploy to Render
- Add persistence
- Add auth
- Add rule engine logic

---

## 1. Switch Alpaca Crypto Feed to GLOBAL

In `app/alpaca_ws.py`, update the endpoint:

```python
ALPACA_CRYPTO_WS_URL = "wss://stream.data.alpaca.markets/v1beta3/crypto/global"
```

Reason:
BTC/USD trades on global venues. US-only feed can be silent for long periods.

---

## 2. Add Explicit Observability Prints (Critical)

### 2.1 Connection lifecycle

Add prints with **prefixes** so logs are grep-friendly.

Inside `AlpacaCryptoStream.start()`:

```python
print("[ALPACA][START] AlpacaCryptoStream.start() invoked")
print(f"[ALPACA][CONNECT] Connecting to {self.ws_url}")
```

After successful connection:

```python
print("[ALPACA][CONNECTED] WebSocket connection established")
```

After auth send:

```python
print("[ALPACA][AUTH_SENT] Auth message sent")
```

After subscription send:

```python
print(f"[ALPACA][SUBSCRIBE_SENT] Subscribed to quotes: {self.symbols}")
```

---

### 2.2 Message receive loop (MOST IMPORTANT)

Inside the receive loop:

```python
print("[ALPACA][WAITING] Awaiting next message from Alpaca...")
raw = await websocket.recv()
print(f"[ALPACA][RECEIVED_RAW] {raw}")
```

If parsing JSON:

```python
print("[ALPACA][PARSE] Parsing incoming message")
```

When quote is detected:

```python
print(f"[ALPACA][QUOTE] symbol={symbol} bid={bid} ask={ask}")
```

If message is ignored:

```python
print("[ALPACA][IGNORED] Message type not relevant")
```

This lets you answer **with certainty**:
- Did Alpaca send *anything*?
- Are we ignoring valid messages?
- Is parsing failing silently?

---

## 3. Market State Construction Tracing

When constructing market_state:

```python
print(f"[MARKET_STATE][BUILD] symbol={symbol} price={price} time={current_time}")
```

Immediately before broadcasting:

```python
print("[MARKET_STATE][BROADCAST] Broadcasting market_state event")
```

---

## 4. Last-Value Caching (Outbound WS Semantics)

In `broadcast.py` (or equivalent):

Add:

```python
self._last_message: str | None = None
```

On broadcast:

```python
self._last_message = message
print("[BROADCAST][CACHE] Updated last market_state")
```

On client connect:

```python
print("[BROADCAST][CLIENT_CONNECT] New WS client connected")

if self._last_message:
    print("[BROADCAST][SEND_CACHED] Sending last market_state to new client")
    await websocket.send_text(self._last_message)
else:
    print("[BROADCAST][NO_CACHE] No market_state cached yet")
```

This makes WS behavior **deterministic**.

---

## 5. Add Root Endpoint (UX + Debug)

In `app/main.py`:

```python
@app.get("/")
def root():
    return {
        "status": "ok",
        "service": "market_state_aggregator",
        "note": "service running, check /ws/market-state for stream"
    }
```

This prevents confusion from 404s and helps with sanity checks.

---

## 6. Local Validation Checklist (MANDATORY)

### 6.1 Start locally

```bash
uvicorn app.main:app --reload
```

---

### 6.2 Watch logs (expected sequence)

You MUST see, in order:

```
[ALPACA][START]
[ALPACA][CONNECT]
[ALPACA][CONNECTED]
[ALPACA][AUTH_SENT]
[ALPACA][SUBSCRIBE_SENT]
[ALPACA][WAITING]
[ALPACA][RECEIVED_RAW] ...
[ALPACA][QUOTE] ...
[MARKET_STATE][BUILD]
[MARKET_STATE][BROADCAST]
```

If it breaks:
- Last printed line tells you **exactly where**

---

### 6.3 Test outbound WS locally

In another terminal:

```bash
wscat -c ws://127.0.0.1:8000/ws/market-state
```

Expected:

- Immediate cached market_state
- Continuous updates thereafter

---

## 7. Pass Criteria (Do NOT skip)

This step is considered **DONE** only if:

- Alpaca raw messages are printed
- Quotes are detected
- market_state is built
- Broadcast happens
- WS client receives data
- Root `/` returns JSON

Only AFTER this passes do we deploy.

---

## 8. Why This Step Exists (Intent)

This removes *all ambiguity*:

- No guessing whether Alpaca is quiet
- No wondering if WS is broken
- No silent failures
- No Render-specific confusion

After this, production issues become **pure deployment**, not logic.

---

## Next Step (After PASS)

Proceed to:
- Production deploy
- Minimal prod verification
- Rule engine integration

DO NOT deploy until this step passes locally.
