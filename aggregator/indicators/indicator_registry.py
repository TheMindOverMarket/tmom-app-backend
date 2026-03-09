import logging
from typing import Any, Callable, Dict, List, Optional
import numpy as np
from aggregator.indicators.ta_lib_planner import IndicatorExecutionPlan, build_talib_execution_plans
from aggregator.indicators.symbol_state import SymbolState

logger = logging.getLogger(__name__)

class IndicatorRegistry:
    """
    Generic TA-Lib layer. Manages registration and computation of indicators.
    """
    def __init__(self):
        self.plans: Dict[str, List[IndicatorExecutionPlan]] = {}

    def clear(self):
        """
        Clears all registered indicators.
        """
        self.plans = {}
        logger.info("Indicator registry cleared.")

    def register(self, name: str, timeframe: str = "1m", params: Optional[Dict[str, Any]] = None):
        """
        Register a single TA-Lib indicator.
        """
        metric_def = {
            "name": name,
            "params": params or {}
        }
        
        new_plans = build_talib_execution_plans([metric_def])
        if timeframe not in self.plans:
            self.plans[timeframe] = []
            
        self.plans[timeframe].extend(new_plans)
        logger.info(f"Registered {name} for {timeframe}.")

    def compute_for_timeframe(self, symbol_state: SymbolState, timeframe: str):
        """
        Compute all registered indicators for a specific timeframe and cache the results.
        Only called when a candle for that timeframe closes.
        """
        # Get the right source of candles
        if timeframe == "1m":
            candles = list(symbol_state.closed_1m_candles)
        else:
            candles = list(symbol_state.derived_timeframes.get(timeframe, []))

        if not candles:
            return

        # Prepare numpy arrays for TA-Lib
        closes = np.array([c.close for c in candles], dtype=float)
        highs = np.array([c.high for c in candles], dtype=float)
        lows = np.array([c.low for c in candles], dtype=float)
        volumes = np.array([c.volume for c in candles], dtype=float)
        opens = np.array([c.open for c in candles], dtype=float)

        input_map = {
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": volumes
        }

        timeframe_plans = self.plans.get(timeframe, [])
        results = {}
        for plan in timeframe_plans:
            try:
                # TA-Lib Abstract API: pass the input map and parameters.
                # The abstract function intelligently selects the required fields (open, high, low, close, volume)
                # from the input map. This resolves the 'Not enough price arguments' error caused by 
                # attempting to pass price arrays as individual keyword arguments.
                res = plan.function(input_map, **plan.params)

                # Handle multi-output vs single-output
                if isinstance(res, (list, tuple, np.ndarray)):
                    # Most abstract functions return arrays. We want the latest non-nan value.
                    if isinstance(res, (list, tuple)):
                        # Some return multiple arrays (e.g. BBANDS)
                        for i, name in enumerate(plan.output_fields):
                            val = res[i][-1]
                            if not np.isnan(val):
                                results[name] = float(val)
                    else:
                        # Single array return
                        val = res[-1]
                        if not np.isnan(val):
                            results[plan.output_fields[0]] = float(val)
                else:
                    if not np.isnan(res):
                        results[plan.output_fields[0]] = float(res)

            except Exception as e:
                logger.error(f"Failed to compute {plan.name} for {symbol_state.symbol} on {timeframe}: {e}")

        # Update cache
        symbol_state.indicator_cache[timeframe] = results
