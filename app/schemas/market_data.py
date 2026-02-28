from pydantic import BaseModel
from typing import List
from datetime import datetime

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
