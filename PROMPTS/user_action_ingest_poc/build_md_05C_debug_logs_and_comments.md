# Build MD 5C — Debug Logs and Intent Comments

## Purpose

Improve debuggability and maintainability by adding **targeted debug logs**
and **intent-explaining comments** around critical runtime boundaries.

This step adds *observability*, not new behavior.

---

## In Scope

### 1) Lifecycle Debug Logs

Add logs at **state transitions only** (not per message):

#### Alpaca WebSocket lifecycle
- `[ALPACA][CONNECTING]`
- `[ALPACA][CONNECTED]`
- `[ALPACA][SHUTDOWN_SIGNAL]`
- `[ALPACA][CLOSED]`

#### Background task lifecycle
- `[STREAM][STARTED]`
- `[STREAM][STOPPING]`
- `[STREAM][EXITED_CLEANLY]`

#### Broadcast lifecycle
- `[BROADCAST][MARKET_STATE][EMIT]`
- `[BROADCAST][USER_ACTIVITY][EMIT]`
- `[BROADCAST][CLIENT_DISCONNECTED]`

Logs must help answer:
- *What stopped?*
- *Why did it stop?*
- *Was this expected?*

---

### 2) Intent Comments (Required)

Add short comments explaining:
- Why shutdown signals exist
- Why CancelledError / ConnectionClosed are caught
- Why sockets are explicitly closed
- Why tasks are awaited during shutdown

Comments should explain **intent**, not restate code.

---

## Out of Scope (Explicit)

- No logic changes
- No schema changes
- No new endpoints
- No reconnection or retry logic
- No performance logging
- No metric systems

---

## Success Criteria

This step is complete if:

1. Logs clearly show:
   - startup
   - normal running
   - shutdown sequence
2. Shutdown logs are distinguishable from runtime errors
3. Comments make shutdown and lifecycle decisions obvious
4. No behavior changes occur

---

## Guardrails

- Do NOT add logs inside hot loops
- Do NOT introduce new abstractions
- Do NOT change program behavior
