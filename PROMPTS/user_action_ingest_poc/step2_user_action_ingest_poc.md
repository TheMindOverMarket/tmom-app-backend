# UserAction Ingest — wOOz PoC  
## Step 2: Event Definitions and Attachment States

---

## 1. Overview

This step defines the **canonical event schemas** emitted by the service and the **attachment state model** used to express the availability and freshness of market context for each user action.

These definitions are intentionally **data-only**.  
They do not encode interpretation, scoring, or enforcement logic.

---

## 2. Event Types

The service emits two independent event streams:

1. **MarketStateEvent** — best-effort market snapshots
2. **UserActionEvent** — atomic records of user trading actions

Streams are emitted independently but are **causally joinable** via explicit references.

---

## 3. MarketStateEvent (PoC)

### Purpose
Represents the latest known market snapshot for a given symbol at a point in time.

### Schema
```json
MarketStateEvent {
  market_state_id: string,
  symbol: string,
  price: number,
  timestamp: number
}
```

### Field Semantics
- `market_state_id` — Unique identifier for this snapshot
- `symbol` — Canonical instrument identifier
- `price` — Last traded price (or equivalent)
- `timestamp` — Time at which this snapshot was observed by the service

### Notes
- Only the **latest snapshot per symbol** is retained in memory
- No assumptions are made about update frequency or continuity

---

## 4. UserActionEvent (PoC)

### Purpose
Represents an atomic user trading action annotated with best-effort market context.

### Schema
```json
UserActionEvent {
  action_id: string,
  user_id: string,
  symbol: string,
  action_type: string,
  quantity: number,
  price: number | null,
  order_type: string,
  timestamp_client: number,
  timestamp_server: number,

  market_state_ref: string | null,
  market_ref_timestamp: number | null,
  market_ref_age_ms: number | null,
  attachment_state: string
}
```

### Core Fields
- `action_id` — Server-generated unique identifier
- `user_id` — Actor identifier
- `symbol` — Canonical instrument identifier
- `action_type` — buy | sell | add | reduce
- `quantity` — Absolute size of the action
- `price` — Execution or intent price (nullable for market orders)
- `order_type` — market | limit | stop
- `timestamp_client` — Time reported by the client
- `timestamp_server` — Authoritative ingest time

---

## 5. Attachment State Model

Every `UserActionEvent` MUST declare exactly one attachment state.

### Allowed Values
- `ATTACHED`
- `ATTACHED_STALE`
- `UNATTACHED`

### Semantics

#### ATTACHED
- A MarketStateEvent exists for the symbol
- `market_ref_timestamp <= timestamp_server`
- Market snapshot age is within acceptable bounds

#### ATTACHED_STALE
- A MarketStateEvent exists for the symbol
- `market_ref_timestamp <= timestamp_server`
- Market snapshot age exceeds freshness threshold

#### UNATTACHED
- No MarketStateEvent was available for the symbol at ingest time

Attachment state explicitly encodes uncertainty and MUST NOT be inferred downstream.

---

## 6. Join Contract for Downstream Consumers

Downstream systems are expected to:

- Join `UserActionEvent` to `MarketStateEvent` using `market_state_ref`
- Use `attachment_state` to determine confidence or eligibility
- Treat `UNATTACHED` events as valid but context-free

Downstream systems MUST NOT:

- Assume continuous market data
- Infer attachment state from timestamps
- Discard events solely due to missing market context

---

## 7. Design Guarantees

- User actions are **never dropped**
- Market context is **best-effort**
- Uncertainty is **explicit and machine-readable**
- Interpretation remains **strictly downstream**

---

## End of Step 2
