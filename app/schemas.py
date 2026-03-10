from pydantic import BaseModel
from typing import Dict, Optional, Any

from pydantic import model_validator

class MarketStateEvent(BaseModel):
    event_type: str = "market_state"
    symbol: str
    current_time: str
    price: float
    high: float
    low: float
    metrics: Dict[str, float] = {}
    indicator_values: Dict[str, Dict[str, float]]

    @model_validator(mode="before")
    @classmethod
    def compute_metrics(cls, values: Any) -> Any:
        if isinstance(values, dict):
            # Compute metrics from indicator_values if not explicitly provided
            if "metrics" not in values and "indicator_values" in values:
                metrics = {}
                for tf, tf_metrics in values["indicator_values"].items():
                    for k, v in tf_metrics.items():
                        key = k if tf == "1m" else f"{k}_{tf}"
                        try:
                            # Rely on Pydantic's float casting downstream, but handle dict safely
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
    timestamp_alpaca: float
    timestamp_server: float
    
    # --- Enrichment Fields (Market Context) ---
    
    # capturing: The reliability status of the market data join.
    # why: Tells the consumer if they can trust the price context. "ATTACHED" = reliable.
    market_attachment_state: Optional[str] = None
    
    # capturing: The unique ID (or timestamp-key) of the exact MarketStateEvent that was attached.
    # why: Allows the consumer to join this event back to the specific market quote in the db/logs.
    market_snapshot_id: Optional[str] = None
    
    # capturing: The milliseconds elapsed between the MarketState creation and this UserActivity.
    # why: Measures "data freshness". Lower is better. If this is high (>5000ms), state becomes "ATTACHED_STALE".
    market_ref_age_ms: Optional[float] = None


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


class RuleIngestRequest(BaseModel):
    rule_nl: str
    user_id: Optional[str] = "default_user"
    playbook_id: Optional[str] = "default_playbook"


class RuleIngestResponse(BaseModel):
    ruleId: str
    status: str


