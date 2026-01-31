# Build MD 3 — Emit UserActivityEvent to Downstream Rule Engine

## Purpose

Emit each normalized `UserActivityEvent` to a downstream rule engine in a **push-based,
event-driven** manner.

This step defines the **emission contract** and mechanism, without introducing market
context, scoring, or persistence.

---

## In Scope

- Define a single downstream emission interface for `UserActivityEvent`
- Emit exactly one downstream event per normalized user activity
- Ensure emission is non-blocking and best-effort
- Preserve existing logs

---

## Out of Scope (Explicit)

- Market data joins or enrichment
- Rule evaluation or scoring
- Persistence, replay, or queues
- HTTP APIs or polling
- Exactly-once delivery guarantees

---

## Downstream Emission Contract

Each emitted event must conform to the existing `UserActivityEvent` schema.

### Emission Semantics

- Emission is **push-based**
- Emission occurs immediately after normalization
- Emission failure must NOT prevent logging or processing of subsequent events

---

## Allowed Emission Mechanisms (choose one)

Exactly ONE of the following mechanisms must be implemented:

1. **In-process broadcast**
   - Async callback / channel / pub-sub pattern
2. **WebSocket fan-out**
   - Internal WS endpoint for consumers
3. **Structured stdout emission**
   - Single-line JSON event with a stable prefix

The mechanism must be clearly identifiable and documented in code.

---

## Observability Requirements

For each emitted event, emit an observable log:

```
[USER_ACTIVITY][EMITTED] <UserActivityEvent payload>
```

This log must occur regardless of downstream success.

---

## Success Criteria

This step is complete if:

- Each normalized `UserActivityEvent` is emitted downstream
- Exactly one downstream emission occurs per activity
- Emission is non-blocking
- Failures do not crash the ingestion loop
- Emission logs are observable

---

## Guardrails

- Do NOT modify Alpaca connectivity or normalization logic
- Do NOT introduce market context
- Do NOT introduce persistence or retries
- Do NOT require downstream polling

---

## Non-Goals

- Delivery guarantees
- Backpressure handling
- Consumer authentication
