# UserAction Ingest — wOOz PoC  
## Step 5: Verification, Observability, and PoC Success Criteria

---

## 1. Purpose

This step defines how the UserAction Ingest service can be **verified, observed, and validated end-to-end** during the wOOz PoC.

The goal is not production monitoring, but to:
- Prove correctness of the ingest pipeline
- Ensure joinability with downstream consumers
- Detect failure modes early
- Provide confidence that the design works under real conditions

---

## 2. Verification Principles

Verification in the PoC focuses on **event correctness**, not throughput or durability.

Key principles:
- Every user action must be observable
- Attachment state must be explainable
- No implicit assumptions are allowed downstream
- Failures must surface as data, not silence

---

## 3. Required Observability Signals

The service MUST emit structured logs or events for the following:

### 3.1 UserAction Ingest Log

Emitted on every successful ingest.

```json
{
  "event": "user_action_ingested",
  "action_id": "string",
  "symbol": "string",
  "attachment_state": "ATTACHED | ATTACHED_STALE | UNATTACHED",
  "market_ref_age_ms": number | null,
  "timestamp_server": number
}
```

---

### 3.2 MarketState Update Log

Emitted whenever the latest market state for a symbol is updated.

```json
{
  "event": "market_state_updated",
  "symbol": "string",
  "market_state_id": "string",
  "timestamp": number
}
```

---

### 3.3 Context Downgrade Log

Emitted when market context cannot be safely attached.

```json
{
  "event": "market_context_downgraded",
  "symbol": "string",
  "reason": "missing | stale | future_timestamp",
  "timestamp_server": number
}
```

---

## 4. Downstream Verification Strategy

Downstream consumers (e.g. rules engine) should verify:

1. Every UserActionEvent appears exactly once
2. attachment_state matches expectations given market feed behavior
3. market_ref_age_ms aligns with observed market data gaps
4. UNATTACHED events are handled explicitly (not dropped)

The ingest service does not enforce correctness downstream but enables verification.

---

## 5. PoC Test Scenarios

The following scenarios MUST be exercised during the PoC:

### 5.1 Normal Flow
- MarketState updates flowing normally
- UserAction ingested with ATTACHED state

### 5.2 Stale Market Data
- Pause market feed
- UserAction ingested with ATTACHED_STALE

### 5.3 Missing Market Data
- No market state available
- UserAction ingested with UNATTACHED

### 5.4 Future Timestamp Injection
- Inject market state with future timestamp
- UserAction ingested with UNATTACHED
- Context downgrade logged

---

## 6. PoC Success Criteria

The PoC is considered successful if:

- No valid user action is ever dropped
- All attachment states are observable and explainable
- Downstream consumers can join streams without guessing
- Edge cases are handled as data, not errors

---

## 7. Explicit Non-Goals

This step does NOT require:
- Metrics dashboards
- Alerting systems
- Persistent audit logs
- Replay infrastructure

---

## End of Step 5
