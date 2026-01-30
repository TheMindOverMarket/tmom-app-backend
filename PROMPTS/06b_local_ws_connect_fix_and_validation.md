# 06b_local_ws_connect_fix_and_validation.md

## Goal

Fix a **deterministic websocket hang** during Alpaca crypto WS connection and re-validate local end-to-end flow with full observability.

This step exists because:
- `await websockets.connect()` is hanging silently
- No auth / subscribe / receive steps are reached
- This must be fixed before any deployment

---

## Scope (Strict)

This step will:

- Add explicit websocket connection parameters (ping + timeouts)
- Keep crypto feed = `crypto/global`
- Preserve all observability prints from step 06
- Re-validate locally

This step will NOT:

- Change architecture
- Add persistence
- Deploy to Render
- Modify schemas

---

## 1. Fix WebSocket Connection Hang (CRITICAL)

In `app/alpaca_ws.py`, update the websocket connect call.

### BEFORE

```python
async with websockets.connect(self.ws_url) as websocket:
```

### AFTER (REQUIRED)

```python
async with websockets.connect(
    self.ws_url,
    ping_interval=20,
    ping_timeout=20,
    open_timeout=10,
    close_timeout=5,
    max_queue=None,
) as websocket:
```

Reason:
- Prevents silent handshake hangs
- Forces deterministic connect/fail
- Required for Alpaca crypto WS with python `websockets`

---

## 2. Observability (Do NOT remove)

Ensure the following prints still exist and fire in order:

```text
[ALPACA][START]
[ALPACA][CONNECT]
[ALPACA][CONNECTED]
[ALPACA][AUTH_SENT]
[ALPACA][SUBSCRIBE_SENT]
[ALPACA][WAITING]
[ALPACA][RECEIVED_RAW]
```

If `[CONNECTED]` does not appear, connection is still failing.

---

## 3. Local Validation (MANDATORY)

### 3.1 Start server

```bash
uvicorn app.main:app --reload
```

---

### 3.2 Expected log sequence (non-negotiable)

Within 5–10 seconds you MUST see:

```
[ALPACA][CONNECT]
[ALPACA][CONNECTED]
[ALPACA][AUTH_SENT]
[ALPACA][SUBSCRIBE_SENT]
```

Then continuously:

```
[ALPACA][RECEIVED_RAW]
[ALPACA][QUOTE]
[MARKET_STATE][BUILD]
[MARKET_STATE][BROADCAST]
```

---

### 3.3 Test outbound WS locally

```bash
wscat -c ws://127.0.0.1:8000/ws/market-state
```

Expected:
- Immediate cached market_state
- Continuous updates

---

## 4. Pass Criteria (DO NOT SKIP)

This step passes ONLY if:

- Alpaca raw messages are printed
- Quote messages are detected
- market_state is built
- Broadcast logs appear
- WS client receives payloads

If any condition fails:
- Report the **last printed log line**
- Do NOT attempt fixes

---

## 5. Why This Fix Matters

Without explicit ping + timeouts:
- `websockets.connect()` may hang forever
- No exception is raised
- Downstream logic never runs

This is a known Alpaca + python-websockets interaction issue.

---

## Next Step (After PASS)

ONLY after this passes locally:
- Deploy to Render
- Run minimal prod verification
- Stop touching infra

