# Build MD 1 — Alpaca trade_updates Ingestion (Execution Activity)

## Purpose

Add ingestion of **user execution activity** from Alpaca via the **Trading WebSocket**
(`trade_updates` stream).

This step establishes the foundation for propagating authoritative user activity
(events such as new orders, partial fills, fills, cancels, rejects) downstream.

This step focuses on **connectivity and receipt only**.

---

## In Scope

- Connect to Alpaca **Trading WebSocket** (paper or live)
- Authenticate successfully
- Subscribe to the `trade_updates` stream
- Receive raw `trade_updates` messages
- Log each received message in an observable way

---

## Out of Scope (Explicit)

- Event normalization or schemas
- Market data joins
- Attachment / freshness logic
- Rule engine emission
- Persistence or replay
- HTTP APIs
- Trading decisions or interpretations

---

## Input Source

**Alpaca Trading WebSocket**
- Stream: `trade_updates`
- Event examples:
  - new
  - partial_fill
  - fill
  - canceled
  - rejected

Alpaca is treated as **authoritative** for execution state.

---

## Emission / Observability Requirements

For every received `trade_updates` message, the service must emit an observable log:

```
[ALPACA][TRADE_UPDATE][RECEIVED] <raw message>
```

- The raw payload is acceptable
- No transformation is required at this step

---

## Success Criteria

This step is complete if:

- The service establishes a WebSocket connection to Alpaca Trading
- Authentication succeeds
- The service subscribes to `trade_updates`
- At least one raw `trade_updates` message is received and logged
- Existing market data ingestion is not broken or modified

---

## Guardrails

- Do NOT modify existing market data WebSocket logic
- Do NOT introduce schemas or derived fields
- Do NOT attach market context
- Do NOT emit downstream rule events yet

---

## Non-Goals

- Reliability guarantees
- Backfill or replay
- Handling reconnections
- Ensuring completeness of fills
