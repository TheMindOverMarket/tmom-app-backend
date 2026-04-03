import uuid
from datetime import datetime
from typing import Optional, Dict, List, Any
from pydantic import BaseModel, model_validator
from app.models import SessionStatus, SessionEventType, Playbook, User, GenerationStatus
from app.markets import build_market_context, normalize_market_symbol

# --- Core Event Schemas (Upstream Alpaca/Aggregator) ---

class MarketStateEvent(BaseModel):
    event_type: str = "market_state"
    symbol: str
    timestamp: str # ISO-8601 UTC
    current_time: str # Legacy support
    price: float
    high: float
    low: float
    vwap: Optional[float] = None
    close_5m: Optional[float] = None
    prior_candle_high_5m: Optional[float] = None
    prior_candle_low_5m: Optional[float] = None
    metrics: Dict[str, float] = {}
    indicator_values: Dict[str, Dict[str, float]]

    @model_validator(mode="before")
    @classmethod
    def compute_metrics(cls, values: Any) -> Any:
        if isinstance(values, dict):
            if "metrics" not in values and "indicator_values" in values:
                metrics = {}
                for tf, tf_metrics in values["indicator_values"].items():
                    for k, v in tf_metrics.items():
                        key = k if tf == "1m" else f"{k}_{tf}"
                        try:
                            metrics[key] = float(v)
                        except (ValueError, TypeError):
                            pass
                values["metrics"] = metrics
        return values


class UserActivityEvent(BaseModel):
    activity_id: str
    alpaca_event_type: str
    order_id: str
    symbol: str
    side: str
    qty: float
    filled_qty: float
    price: Optional[float]
    timestamp: str # ISO-8601 UTC standard for chart sync
    timestamp_alpaca: float
    timestamp_server: float
    market_attachment_state: Optional[str] = None
    market_snapshot_id: Optional[str] = None
    market_ref_age_ms: Optional[float] = None

# --- User Schemas ---

class UserCreate(BaseModel):
    email: str

class UserUpdate(BaseModel):
    email: Optional[str] = None

# --- Playbook Schemas ---

HARDCODED_PROMPT = """
I'm using BTC.

1. Setup Logic (Deterministic Inputs)

Derived State:
    - Session VWAP (UTC daily reset)
    - 20-period EMA
    - 14-period ATR
    - Rolling volatility regime
    - Daily realized PnL

---

Long Setup

Conditions must ALL be true:
    1. Price < VWAP - 1.5 * ATR
    2. EMA slope > 0
    3. 5-min close back above prior candle high
    4. Not within 10 minutes of previous stop

---

Short Setup
    1. Price > VWAP + 1.5 * ATR
    2. EMA slope < 0
    3. 5-min close below prior candle low
    4. Not within 10 minutes of previous stop

---

2. Entry Rules
    - Market order at next candle open.
    - Max 1 position at a time.
    - No pyramiding.
    - No flipping within 5 minutes.

---

3. Risk Model

Stop: 1 ATR
Target: 2 ATR
Trailing stop activates at +1R
Max daily loss: 3R
Max 5 trades per UTC day
Position size: 1% account risk per trade

---

4. Meta Discipline Rules (Where TMOM Shines)

Hard Constraints:
    - Block trade if daily loss >= 3R
    - Block if > 5 trades
    - Block if position size > 1% risk

Soft Guardrails:
    - Warn if trade taken within 3 minutes of prior close
    - Warn if volatility > 95th percentile
    - Require justification if third consecutive loss

Cooldown:
    - 10 minutes after stop loss
    - 30 minutes after 2 consecutive losses
"""

class PlaybookCreate(BaseModel):
    name: str
    # Temporary/dirty implementation note:
    # user_id must now be provided explicitly by the frontend user picker.
    # This is still not real auth and should be replaced by proper identity/session handling later.
    user_id: uuid.UUID
    market: str = "BTC/USD"
    original_nl_input: str
    context: Optional[Dict[str, Any]] = None
    is_active: bool = True
    generation_status: GenerationStatus = GenerationStatus.COMPLETED
    failure_reason: Optional[str] = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "Sample BTC Ruleset",
                "user_id": "00000000-0000-0000-0000-000000000000",
                "market": "BTC/USD",
                "original_nl_input": HARDCODED_PROMPT,
                "context": {
                    "description": "Auto-generated sample playbook from utility endpoint",
                    "symbol": "BTC/USD"
                },
                "is_active": True
            }
        }
    }

    @model_validator(mode="before")
    @classmethod
    def cast_context_floats(cls, values: Any) -> Any:
        def parse_floats(data: Any) -> Any:
            if isinstance(data, dict):
                return {k: parse_floats(v) for k, v in data.items()}
            elif isinstance(data, list):
                return [parse_floats(v) for v in data]
            elif isinstance(data, str):
                try:
                    return float(data)
                except ValueError:
                    return data
            return data
        if isinstance(values, dict) and values.get("context"):
            values["context"] = parse_floats(values["context"])
        return values

    @model_validator(mode="after")
    def sync_market_context(self) -> "PlaybookCreate":
        self.market = normalize_market_symbol(self.market)
        self.context = build_market_context(self.context, self.market)
        return self

class PlaybookUpdate(BaseModel):
    name: Optional[str] = None
    market: Optional[str] = None
    original_nl_input: Optional[str] = None
    context: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None
    generation_status: Optional[GenerationStatus] = None
    failure_reason: Optional[str] = None

    @model_validator(mode="after")
    def sync_market_context(self) -> "PlaybookUpdate":
        if self.market is not None:
            self.market = normalize_market_symbol(self.market)
            self.context = build_market_context(self.context, self.market)
        elif self.context and self.context.get("symbol"):
            self.market = normalize_market_symbol(self.context["symbol"])
            self.context = build_market_context(self.context, self.market)
        return self

class PlaybookIngest(BaseModel):
    name: str
    user_id: uuid.UUID
    market: str = "BTC/USD"
    original_nl_input: str

    @model_validator(mode="after")
    def normalize_market(self) -> "PlaybookIngest":
        self.market = normalize_market_symbol(self.market)
        return self


class MarketOption(BaseModel):
    symbol: str
    base_asset: str
    quote_asset: str
    display_name: str
    provider: str

class StartStreamsRequest(BaseModel):
    user_id: uuid.UUID
    playbook_id: uuid.UUID

class StartStreamsResponse(BaseModel):
    status: str
    message: str
    playbook: Playbook # Note: SQLModel import

# --- Rule & Condition Schemas ---

class RuleCreate(BaseModel):
    name: str
    description: Optional[str] = None
    category: Optional[str] = "logic"
    playbook_id: uuid.UUID
    is_active: bool = True

class RuleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    is_active: Optional[bool] = None

class RuleIngestRequest(BaseModel):
    rule_nl: str
    user_id: Optional[str] = "default_user"
    playbook_id: Optional[str] = "default_playbook"

class RuleIngestResponse(BaseModel):
    ruleId: str
    status: str

class ConditionCreate(BaseModel):
    rule_id: uuid.UUID
    metric: str
    comparator: str
    value: str
    is_active: bool = True

class ConditionUpdate(BaseModel):
    metric: Optional[str] = None
    comparator: Optional[str] = None
    value: Optional[str] = None
    is_active: Optional[bool] = None

class ConditionEdgeCreate(BaseModel):
    rule_id: uuid.UUID
    parent_condition_id: uuid.UUID
    child_condition_id: uuid.UUID
    logical_operator: str

class ConditionEdgeUpdate(BaseModel):
    logical_operator: Optional[str] = None

# --- Market Data & State Schemas ---

class MarketBar(BaseModel):
    time: int
    open: float
    high: float
    low: float
    close: float

class MarketHistoryResponse(BaseModel):
    symbol: str
    timeframe: str
    data: List[MarketBar]

class MarketStateSnapshot(BaseModel):
    symbol: str
    last_price: float
    last_tick_timestamp_ms: Optional[int] = None
    current_candle_high: float
    current_candle_low: float
    prior_candle_high: Optional[float] = None
    prior_candle_low: Optional[float] = None
    session_high: float
    session_low: float
    vwap: Optional[float] = None
    close_5m: Optional[float] = None
    prior_candle_high_5m: Optional[float] = None
    prior_candle_low_5m: Optional[float] = None
    indicator_values: Dict[str, Dict[str, float]]

# --- Trade Schemas ---

class TradeTriggerRequest(BaseModel):
    symbol: str = "BTC/USD"
    qty: str = "0.001"
    side: str = "buy"
    type: str = "market"
    time_in_force: str = "gtc"

class TradeTriggerResponse(BaseModel):
    status: str
    order_id: Optional[str] = None
    error: Optional[str] = None

# --- Session Analytics Schemas ---

class SessionCreate(BaseModel):
    user_id: uuid.UUID
    playbook_id: uuid.UUID
    session_metadata: Optional[Dict[str, Any]] = None

class SessionUpdate(BaseModel):
    status: Optional[SessionStatus] = None
    session_metadata: Optional[Dict[str, Any]] = None

class SessionRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    playbook_id: uuid.UUID
    start_time: datetime
    end_time: Optional[datetime] = None
    status: SessionStatus
    session_metadata: Optional[Dict[str, Any]] = None
    created_at: datetime

    class Config:
        from_attributes = True

class SessionEventCreate(BaseModel):
    type: SessionEventType
    timestamp: Optional[datetime] = None
    tick: Optional[int] = None
    event_data: Dict[str, Any]
    event_metadata: Optional[Dict[str, Any]] = None

class SessionEventRead(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    type: SessionEventType
    timestamp: datetime
    tick: Optional[int] = None
    event_data: Dict[str, Any]
    event_metadata: Optional[Dict[str, Any]] = None
    created_at: datetime

    class Config:
        from_attributes = True
