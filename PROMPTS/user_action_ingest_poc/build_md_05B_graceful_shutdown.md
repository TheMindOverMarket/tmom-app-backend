# Build MD 5B — Graceful Shutdown of Alpaca WebSocket Tasks

## Purpose

Fix application shutdown failures by ensuring **Alpaca WebSocket background tasks
terminate cleanly** when FastAPI shuts down.

This step addresses observed shutdown errors such as:
- IncompleteReadError
- ConnectionClosedError
- "Application shutdown failed"

This MD focuses ONLY on shutdown correctness.

---

## In Scope

### 1) Explicit Shutdown Signaling

- Introduce a shutdown signal/flag for Alpaca WS loops
- Ensure each WS loop can detect shutdown intent
- Stop awaiting `ws.recv()` indefinitely during shutdown

### 2) WebSocket Closure

- Explicitly close Alpaca WebSocket connections on shutdown
- Do not rely on event loop teardown alone

### 3) Task Cancellation Handling

- Properly handle:
  - `asyncio.CancelledError`
  - `websockets.exceptions.ConnectionClosedError`
- These exceptions must be treated as **expected during shutdown**
- They must NOT propagate and crash the application

### 4) Lifecycle Integration

- Ensure `on_shutdown` awaits background tasks safely
- Background tasks must exit their run loops and return cleanly

---

## Out of Scope (Explicit)

- No WebSocket endpoint changes
- No broadcaster changes
- No schema or payload changes
- No new debug logs (handled in MD 5C)
- No reconnection or retry logic

---

## Success Criteria

This step is complete if:

1. Application shutdown produces **no traceback**
2. Alpaca WS connections are explicitly closed
3. Background tasks exit without raising errors
4. FastAPI logs show clean shutdown completion

---

## Guardrails

- Do NOT ignore exceptions silently outside shutdown context
- Do NOT add new features or refactors
- Do NOT modify behavior during normal operation
