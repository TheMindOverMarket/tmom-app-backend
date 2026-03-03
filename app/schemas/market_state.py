from pydantic import BaseModel
from typing import Dict, Any, Optional

class MarketStateSnapshot(BaseModel):
    """
    Consolidated market state snapshot for the Rule Engine.
    Decoupled from raw providers and candle engines.
    """
    symbol: str
    last_price: float
    
    # Current (forming) candle stats
    current_candle_high: float
    current_candle_low: float
    
    # Prior (closed) candle stats
    prior_candle_high: Optional[float] = None
    prior_candle_low: Optional[float] = None
    
    # Session stats
    session_high: float
    session_low: float
    
    # Indicators (cached)
    # Structure: { "1m": { "EMA": 100.0 }, "5m": { ... } }
    indicator_values: Dict[str, Dict[str, float]]
