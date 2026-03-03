from collections import deque
from typing import Deque, List

class SymbolState:
    """
    Maintains rolling close price history for a symbol.
    """

    def __init__(self, max_lookback: int) -> None:
        self.max_lookback = max_lookback
        self.close_history: Deque[float] = deque(maxlen=max_lookback)

    def update(self, close: float) -> None:
        self.close_history.append(close)

    def get_close_array(self) -> List[float]:
        return list(self.close_history)
