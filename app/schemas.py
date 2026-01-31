from pydantic import BaseModel
from typing import Dict, Optional


class MarketStateEvent(BaseModel):
    event_type: str = "market_state"
    symbol: str
    timestamp: str
    price: float
    metrics: Dict[str, float]


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
