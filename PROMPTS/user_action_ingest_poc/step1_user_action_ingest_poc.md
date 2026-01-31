# UserAction Ingest — wOOz PoC  
## Step 1: Purpose, Scope, and Non-Goals

---

## 1. Purpose

This service ingests **user trading actions** and emits them as **atomic, timestamped events**, optionally annotated with **best-effort market context**, to enable downstream strategy and rules engines to reason about *user behavior in market context*.

The service **does not interpret**, **does not score**, and **does not enforce rules**.  
Its sole responsibility is to **record what happened, when it happened, and what market information was available at that moment**.

---

## 2. Scope (wOOz PoC)

In the wOOz PoC, this service is responsible for:

- Ingesting **UserAction events**
- Attaching **best-effort market state references** at ingest time
- Explicitly classifying the **availability and freshness of market context**
- Emitting events suitable for **downstream joining and rule evaluation**

The service operates **without persistence** and maintains only **minimal in-memory state** required for causal attachment.

---

## 3. Explicit Non-Goals (PoC Constraints)

The following are **intentionally out of scope** for the wOOz PoC:

- Acting as a system of record
- Guaranteeing replayability across restarts
- Ensuring continuous or gap-free market state ingestion
- Reconstructing historical joins post-hoc
- Making trading decisions or recommendations
- Scoring conviction, confidence, or correctness

These constraints are deliberate to keep the PoC **focused on validating downstream strategy logic**, not infrastructure completeness.

---

## 4. Architectural Positioning

This service functions as a **temporal coordination layer**, not a decision engine.

- It emits **atomic events**
- It does **not merge streams into derived objects**
- It provides **explicit causal references** to enable deterministic joins downstream

Downstream consumers (e.g. rules engines) are expected to:

- Consume streams independently
- Join events using provided references
- Apply interpretation, scoring, and enforcement logic

---

## 5. Design Principles (Hard Requirements)

1. **No hindsight**  
   A user action may only reference market state that existed at ingest time.

2. **Explicit uncertainty**  
   Missing or stale market context must be surfaced, never hidden.

3. **Determinism (within process lifetime)**  
   Given identical inputs during a single runtime, outputs are consistent.

4. **Atomicity**  
   User actions are never dropped or rewritten due to missing market data.

5. **Minimal state**  
   Only the latest market snapshot per symbol is retained in memory.

---

## End of Step 1
