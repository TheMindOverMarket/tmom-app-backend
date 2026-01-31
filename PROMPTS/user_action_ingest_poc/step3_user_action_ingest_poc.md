# UserAction Ingest — wOOz PoC  
## Step 3: Ingest Algorithm, Guardrails, and Failure Modes

---

## 1. Purpose

This step defines the **exact ingest-time algorithm** used to process UserAction events, resolve best-effort market context, and assign attachment states.

The algorithm is designed to:
- Preserve causal correctness
- Avoid future data leakage
- Surface uncertainty explicitly
- Operate without persistence (PoC constraint)
- Never drop valid user actions due to market context issues

---

## 2. Configuration (PoC)

The following values are defined as **static configuration** for the PoC and MAY be externalized later.

```text
MARKET_STATE_FRESHNESS_MS = <configured value>
```

This value defines the maximum acceptable age (in milliseconds) of a MarketStateEvent for it to be considered `ATTACHED`.

---

## 3. In-Memory State

The service maintains only the following in-memory structure:

```text
latest_market_state_by_symbol: Map<symbol, MarketStateEvent>
```

No historical market states are retained.

---

## 4. Ingest Algorithm (UserActionEvent)

The following steps MUST be executed in order for each incoming UserAction.

### Step 1 — Validate Input
- Required fields: user_id, symbol, action_type, quantity, timestamp_client
- Normalize symbol to canonical form

### Step 2 — Capture Server Timestamp
- Set `timestamp_server = now()`
- This timestamp is authoritative for context resolution

### Step 3 — Resolve Market State (Best-Effort)
- Lookup `latest_market_state_by_symbol[symbol]`
- If no entry exists, set `attachment_state = UNATTACHED`

### Step 4 — Prevent Future Leakage (Context Downgrade)
- If a MarketStateEvent exists AND `market_ref_timestamp > timestamp_server`:
  - Log warning (potential clock drift or invalid upstream data)
  - Set `attachment_state = UNATTACHED`
  - Proceed to emission (UserAction takes precedence)

This condition indicates upstream clock drift or invalid market data and MUST NOT cause loss of user intent.

### Step 5 — Compute Attachment State
If a MarketStateEvent exists and is valid:

```text
market_ref_age_ms = timestamp_server - market_ref_timestamp

if market_ref_age_ms <= MARKET_STATE_FRESHNESS_MS:
    attachment_state = ATTACHED
else:
    attachment_state = ATTACHED_STALE
```

If no valid MarketStateEvent exists:
```text
attachment_state = UNATTACHED
```

### Step 6 — Emit UserActionEvent
Emit a UserActionEvent containing:
- All core user action fields
- Market reference fields (nullable)
- attachment_state

User actions MUST be emitted regardless of attachment_state.

---

## 5. Failure Modes

### MARKET_STATE_UNAVAILABLE
- Triggered when no MarketStateEvent exists
- Result: UserActionEvent emitted with `UNATTACHED`

### MARKET_STATE_INVALID (Future Timestamp)
- Triggered when market_ref_timestamp > timestamp_server
- Result: UserActionEvent emitted with `UNATTACHED`
- Indicates upstream market data issue

### INVALID_INPUT
- Triggered when required fields are missing or malformed
- Result: Ingest rejected

---

## 6. Guarantees

- User actions are never dropped due to market context issues
- No future market data is ever attached
- All uncertainty is explicitly encoded
- Behavior is deterministic within process lifetime

---

## End of Step 3
