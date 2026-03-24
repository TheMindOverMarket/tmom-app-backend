from pydantic import BaseModel, model_validator
from typing import Dict, Optional, Any

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
    timestamp_alpaca: float
    timestamp_server: float
    market_attachment_state: Optional[str] = None
    market_snapshot_id: Optional[str] = None
    market_ref_age_ms: Optional[float] = None
