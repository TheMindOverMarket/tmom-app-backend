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
    
    # Enrichment Fields
    market_attachment_state: Optional[str] = None
    market_snapshot_id: Optional[str] = None
    market_ref_age_ms: Optional[float] = None
