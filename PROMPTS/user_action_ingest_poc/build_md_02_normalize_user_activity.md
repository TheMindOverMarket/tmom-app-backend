# Build MD 2 — Normalize trade_updates → UserActivityEvent

## Purpose

Transform raw Alpaca `trade_updates` messages into a **normalized, stable internal event**
(`UserActivityEvent`) suitable for downstream consumption.

This step introduces **schemas and deterministic mapping**, but still performs **no market
context joins** and **no rule evaluation**.

---

## In Scope

- Define a `UserActivityEvent` schema
- Parse each raw `trade_updates` message
- Normalize it into exactly one `UserActivityEvent`
- Emit/log the normalized event

---

## Out of Scope (Explicit)

- Market data joins
- Attachment / freshness logic
- Rule engine evaluation
- Persistence or replay
- HTTP APIs

---

## Input Source

**Alpaca Trading WebSocket**
- Stream: `trade_updates`
- Input: raw Alpaca payloads already being received and logged

---

## Normalized Event: UserActivityEvent

Each `trade_updates` message must produce **exactly one** `UserActivityEvent`.

### Required Fields

| Field | Type | Description |
|------|------|-------------|
| activity_id | string | Generated UUID |
| alpaca_event_type | string | Raw Alpaca event type (e.g. new, fill) |
| order_id | string | Alpaca order ID |
| symbol | string | Trading symbol |
| side | string | buy / sell |
| qty | number | Original order quantity |
| filled_qty | number | Filled quantity so far |
| price | number \| null | Filled average price if present |
| timestamp_alpaca | number | Alpaca-provided timestamp (epoch ms) |
| timestamp_server | number | Ingest time (epoch ms) |

### Mapping Rules

- No inference or correction of Alpaca data
- Missing fields must be set to `null`
- UUID generation must be server-side
- Exactly one normalized event per input message

---

## Emission / Observability Requirements

For every normalized event, emit an observable log:

```
[USER_ACTIVITY][NORMALIZED] <UserActivityEvent payload>
```

Raw `[ALPACA][TRADE_UPDATE][RECEIVED]` logs must remain intact.

---

## Success Criteria

This step is complete if:

- A `UserActivityEvent` schema exists
- Every `trade_updates` message produces one normalized event
- Normalized events include all required fields
- Normalized events are logged with the required prefix
- No market joins or rule logic are present

---

## Guardrails

- Do NOT modify Alpaca connectivity logic
- Do NOT attach market context
- Do NOT emit rule-engine-specific outputs
- Do NOT persist events

---

## Non-Goals

- Data validation beyond structural parsing
- Handling malformed Alpaca payloads
- Enrichment or aggregation
