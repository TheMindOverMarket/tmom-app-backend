# Build MD 5A — Split WebSocket Endpoints (No Multiplexing)

## Purpose

Remove ambiguity for consumers by **splitting WebSocket endpoints** so each endpoint emits exactly one event type.

This step focuses ONLY on endpoint separation and emission routing.  
It intentionally does **not** address shutdown hardening or additional debug instrumentation (handled in subsequent MDs).

---

## In Scope

### 1) Two explicit WebSocket endpoints

Create/ensure two distinct WebSocket endpoints:

- `/ws/market-state`
  - Emits **MarketStateEvent only**
- `/ws/user-activity`
  - Emits **UserActivityEvent only** (enriched or not)

Each endpoint MUST have its **own broadcaster instance**.

### 2) Emission routing

- Market ingestion broadcasts ONLY through the market-state broadcaster
- User-activity ingestion broadcasts ONLY through the user-activity broadcaster
- No shared broadcast paths
- No multiplexing on a single socket

### 3) Consumer contract

- Consumers that want market updates connect to `/ws/market-state`
- Consumers that want user activity connect to `/ws/user-activity`
- No requirement to filter by event type on the client

---

## Out of Scope (Explicit)

- Graceful shutdown fixes
- Additional debug logs / comments beyond what already exists
- Schema changes or payload shape changes
- Persistence / replay
- Reconnection logic

---

## Success Criteria

This step is complete if:

1. `/ws/market-state` emits ONLY market state messages (no user activity messages)
2. `/ws/user-activity` emits ONLY user activity messages (no market state messages)
3. Both sockets can have clients connected simultaneously
4. Existing ingestion logic continues to operate (market + trading streams)

---

## Guardrails

- Do NOT change event schemas
- Do NOT introduce new event types
- Do NOT reintroduce multiplexing
