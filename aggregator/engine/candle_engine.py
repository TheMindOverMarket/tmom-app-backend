import logging
from datetime import datetime, timezone
from typing import Dict, Optional
from aggregator.models import NormalizedTick, NormalizedBar
from aggregator.indicators.symbol_state import SymbolState
from aggregator.indicators.indicator_registry import IndicatorRegistry

logger = logging.getLogger(__name__)

class CandleEngine:
    """
    Orchestrates tick ingestion, candle aggregation, and indicator computation.
    """
    def __init__(self, registry: IndicatorRegistry):
        self.registry = registry
        self.symbol_states: Dict[str, SymbolState] = {}

    def get_symbol_state(self, symbol: str) -> SymbolState:
        if symbol not in self.symbol_states:
            self.symbol_states[symbol] = SymbolState(symbol)
        return self.symbol_states[symbol]

    def hydrate_historical_bars(self, symbol: str, bars: list[NormalizedBar]):
        """
        Hydrate the engine with historical bars to warm up indicators and higher timeframes.
        """
        state = self.get_symbol_state(symbol)
        
        # Sort to ensure chronological order
        bars.sort(key=lambda b: b.start_time)
        
        logger.info(f"[CANDLE_ENGINE] Hydrating {symbol} with {len(bars)} historical bars...")
        for bar in bars:
            state.current_1m_candle = bar
            self._finalize_1m_candle(state)
            
        if bars:
            last_bar = bars[-1]
            state.update_last_price(last_bar.close)
            state.last_tick_timestamp_ms = int(last_bar.start_time.timestamp() * 1000)

            # Warm the session VWAP using only the current UTC trading day.
            latest_session_date = last_bar.start_time.astimezone(timezone.utc).date()
            state.reset_vwap(latest_session_date)
            for bar in bars:
                if bar.start_time.astimezone(timezone.utc).date() != latest_session_date:
                    continue
                state.add_vwap_sample(
                    price=bar.close,
                    volume=bar.volume,
                    timestamp=bar.start_time,
                )
            
        # Clear the current candle so the next live tick starts fresh
        state.current_1m_candle = None
        logger.info(f"[CANDLE_ENGINE] Hydration complete for {symbol}. Current 1m closed candles: {len(state.closed_1m_candles)}")


    def ingest_tick(self, tick: NormalizedTick):
        """
        Process a new tick. Updates current candle.
        Checks for minute boundaries to finalize candles and trigger indicators.
        """
        state = self.get_symbol_state(tick.symbol)
        state.update_last_price(tick.price)
        state.last_tick_timestamp_ms = int(tick.timestamp.timestamp() * 1000)

        # UPDATE SESSION VWAP with a UTC day reset boundary
        state.add_vwap_sample(price=tick.price, volume=tick.size, timestamp=tick.timestamp)

        # Truncate to minute
        tick_minute = tick.timestamp.replace(second=0, microsecond=0)

        # Handle candle transition
        if state.current_1m_candle is None:
            state.current_1m_candle = self._create_new_bar(tick, "1m")
        elif tick_minute > state.current_1m_candle.start_time:
            # A new minute has started. Finalize the PREVIOUS minute.
            self._finalize_1m_candle(state)
            # Start the NEW minute
            state.current_1m_candle = self._create_new_bar(tick, "1m")
        else:
            # Same minute, update the bar
            self._update_bar(state.current_1m_candle, tick)

    def _create_new_bar(self, tick: NormalizedTick, timeframe: str) -> NormalizedBar:
        return NormalizedBar(
            symbol=tick.symbol,
            timeframe=timeframe,
            open=tick.price,
            high=tick.price,
            low=tick.price,
            close=tick.price,
            volume=tick.size,
            start_time=tick.timestamp.replace(second=0, microsecond=0)
        )

    def _update_bar(self, bar: NormalizedBar, tick: NormalizedTick):
        bar.high = max(bar.high, tick.price)
        bar.low = min(bar.low, tick.price)
        bar.close = tick.price
        bar.volume += tick.size

    def _finalize_1m_candle(self, state: SymbolState):
        """
        Closes the 1m candle, derives higher timeframes, and triggers indicator re-calc.
        """
        closed_bar = state.current_1m_candle
        if not closed_bar:
            return

        state.closed_1m_candles.append(closed_bar)
        
        # Trigger indicators for 1m
        self.registry.compute_for_timeframe(state, "1m")

        # Derive 5m
        if closed_bar.start_time.minute % 5 == 4:
            self._derive_timeframe(state, "5m", 5)
            self.registry.compute_for_timeframe(state, "5m")

        # Derive 15m
        if closed_bar.start_time.minute % 15 == 14:
            self._derive_timeframe(state, "15m", 15)
            self.registry.compute_for_timeframe(state, "15m")

    def _derive_timeframe(self, state: SymbolState, timeframe: str, window: int):
        """
        Aggregate last 'window' 1m candles into a higher timeframe bar.
        """
        if len(state.closed_1m_candles) < window:
            return

        last_n = list(state.closed_1m_candles)[-window:]
        
        derived_bar = NormalizedBar(
            symbol=state.symbol,
            timeframe=timeframe,
            open=last_n[0].open,
            high=max(b.high for b in last_n),
            low=min(b.low for b in last_n),
            close=last_n[-1].close,
            volume=sum(b.volume for b in last_n),
            start_time=last_n[0].start_time
        )
        state.derived_timeframes[timeframe].append(derived_bar)
        logger.debug(f"Derived {timeframe} bar for {state.symbol} at {derived_bar.start_time}")

    def clear_symbol_state(self, symbol: str):
        """
        Clears the state for a specific symbol. Useful for freeing resources when a session ends.
        """
        if symbol in self.symbol_states:
            logger.info(f"[CANDLE_ENGINE] Clearing state for {symbol}")
            del self.symbol_states[symbol]

    def clear_all(self):
        """
        Clears all symbol states.
        """
        logger.info("[CANDLE_ENGINE] Clearing all symbol states")
        self.symbol_states = {}
