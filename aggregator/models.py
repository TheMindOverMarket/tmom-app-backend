from datetime import datetime
from dataclasses import dataclass
from typing import Optional

@dataclass
class NormalizedTick:
    symbol: str
    timestamp: datetime
    price: float
    size: float

@dataclass
class NormalizedQuote:
    symbol: str
    timestamp: datetime
    bid: float
    ask: float

@dataclass
class NormalizedBar:
    symbol: str
    timeframe: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    start_time: datetime
