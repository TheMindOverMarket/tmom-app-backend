from pydantic import BaseModel
from typing import Dict


class MarketStateEvent(BaseModel):
    event_type: str = "market_state"
    symbol: str
    timestamp: str
    price: float
    metrics: Dict[str, float]
