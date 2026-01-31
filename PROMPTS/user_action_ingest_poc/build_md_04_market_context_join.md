# Build MD 4 — Join UserActivityEvent with Market Context

## Purpose

Enrich each normalized `UserActivityEvent` with **best-effort market context**
using the latest available market snapshot for the same symbol.

This step introduces **context attachment** and **explicit uncertainty signaling**
without adding persistence, scoring, or rule evaluation.

---

## In Scope

- Lookup latest market snapshot for the activity symbol
- Attach market reference metadata to the emitted event
- Classify attachment state explicitly
- Preserve original UserActivityEvent fields

---

## Out of Scope (Explicit)

- Rule evaluation or scoring
- Persistence or replay
- Exactly-once guarantees
- Backpressure handling
- Market prediction or inference

---

## Inputs

- `UserActivityEvent` (from Build MD 2)
- Latest market snapshot per symbol (already ingested via market WS)

---

## Attachment Model

Each emitted event must include **market attachment metadata**.

### Required Fields (to add)

| Field | Type | Description |
|------|------|-------------|
| market_attachment_state | string | ATTACHED \| ATTACHED_STALE \| UNATTACHED |
| market_snapshot_id | string \| null | Identifier of attached snapshot |
| market_ref_age_ms | number \| null | Age of snapshot relative to activity |

---

## Attachment Rules

- **ATTACHED**
  - Market snapshot exists for symbol
  - Snapshot timestamp ≤ activity timestamp
  - Snapshot age ≤ MARKET_STATE_FRESHNESS_MS

- **ATTACHED_STALE**
  - Market snapshot exists
  - Snapshot timestamp ≤ activity timestamp
  - Snapshot age > MARKET_STATE_FRESHNESS_MS

- **UNATTACHED**
  - No snapshot exists for symbol
  - OR snapshot timestamp > activity timestamp
  - OR snapshot is invalid / missing timestamp

---

## Guardrails (Critical)

- User activity events must **never be dropped**
- If attachment fails, downgrade to `UNATTACHED`
- Do NOT attach future-dated market data
- Do NOT block or delay emission

---

## Emission Requirements

- Emit exactly one enriched event per activity
- Emit observable log:

```
[USER_ACTIVITY][ENRICHED] <full payload>
```

- Raw and normalized logs must remain intact

---

## Success Criteria

This step is complete if:

- Market context is attached when valid
- Stale and missing data are explicitly labeled
- No future market data leakage occurs
- Emission continues even on attachment failure

---

## Non-Goals

- Market data correctness guarantees
- Multi-snapshot attachment
- Historical joins
