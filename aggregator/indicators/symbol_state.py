import copy
from collections import deque
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
from aggregator.models import NormalizedBar

class SymbolState:
    """
    Maintains per-symbol state including candle history and indicator cache.
    """

    def __init__(self, symbol: str, max_lookback: int = 200) -> None:
        self.symbol = symbol
        self.max_lookback = max_lookback
        
        # 1-minute base candles
        self.current_1m_candle: Optional[NormalizedBar] = None
        self.closed_1m_candles: deque[NormalizedBar] = deque(maxlen=max_lookback)
        
        # Derived timeframes (e.g., '5m', '15m') -> list/deque of bars
        self.derived_timeframes: Dict[str, deque[NormalizedBar]] = {
            "5m": deque(maxlen=max_lookback),
            "15m": deque(maxlen=max_lookback)
        }
        
        # Indicator results (cached)
        # Structure: { "1m": { "EMA_14": 123.45 }, "5m": { ... } }
        self.indicator_cache: Dict[str, Dict[str, float]] = {
            "1m": {},
            "5m": {},
            "15m": {}
        }
        
        # Session high/low tracking
        self.session_high: float = float('-inf')
        self.session_low: float = float('inf')
        
        self.last_price: float = 0.0
        self.last_tick_timestamp_ms: Optional[int] = None

    def update_last_price(self, price: float):
        self.last_price = price
        if price > self.session_high:
            self.session_high = price
        if price < self.session_low:
            self.session_low = price

    def get_snapshot(self) -> Dict[str, Any]:
        """
        Returns a dictionary representation of the current state, 
        suitable for MarketStateSnapshot schema.
        """
        prior_1m = self.closed_1m_candles[-1] if self.closed_1m_candles else None
        
        return {
            "symbol": self.symbol,
            "last_price": self.last_price,
            "last_tick_timestamp_ms": self.last_tick_timestamp_ms,
            "current_candle_high": self.current_1m_candle.high if self.current_1m_candle else self.last_price,
            "current_candle_low": self.current_1m_candle.low if self.current_1m_candle else self.last_price,
            "prior_candle_high": prior_1m.high if prior_1m else None,
            "prior_candle_low": prior_1m.low if prior_1m else None,
            "session_high": self.session_high,
            "session_low": self.session_low,
            "indicator_values": copy.deepcopy(self.indicator_cache)
        }
