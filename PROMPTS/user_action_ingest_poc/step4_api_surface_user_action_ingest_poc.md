# UserAction Ingest — wOOz PoC  
## Step 4: API Surface and Contracts

---

## 1. Purpose

This step defines the **external API surface** of the UserAction Ingest service.

It specifies:
- Supported endpoints
- Request and response schemas
- Error handling behavior

No persistence, streaming, or transport optimizations are introduced.

---

## 2. API Style

- Protocol: HTTP (REST)
- Encoding: JSON
- Transport guarantees: best-effort
- Ordering guarantees: none across requests

---

## 3. Endpoints

### 3.1 Ingest User Action

**Endpoint**
```
POST /user-action
```

**Purpose**  
Accept a single user trading action and emit a corresponding UserActionEvent.

---

## 4. Request Schema

```json
{
  "user_id": "string",
  "symbol": "string",
  "action_type": "buy | sell | add | reduce",
  "quantity": number,
  "price": number | null,
  "order_type": "market | limit | stop",
  "timestamp_client": number
}
```

### Field Notes
- `timestamp_client` is informational only
- Server time is authoritative for ingestion

---

## 5. Response Schema (Success)

```json
{
  "action_id": "string",
  "attachment_state": "ATTACHED | ATTACHED_STALE | UNATTACHED",
  "timestamp_server": number,
  "market_ref_age_ms": number | null
}
```

The response reflects **ingest outcome**, not trade outcome.

---

## 6. Error Handling

### Invalid Input
- HTTP 400
- Missing or malformed required fields

### Ingest Success with Context Failure
- HTTP 200
- `attachment_state = UNATTACHED`

Market context issues MUST NOT cause request failure.

---

## 7. Guarantees

- A valid UserAction request is always recorded
- Market context failures are downgraded, not rejected
- Responses are deterministic within process lifetime

---

## End of Step 4
