import logging
import re
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional
import numpy as np
import talib
from aggregator.indicators.ta_lib_planner import IndicatorExecutionPlan, build_talib_execution_plans
from aggregator.indicators.symbol_state import SymbolState

logger = logging.getLogger(__name__)

@dataclass
class DynamicIndicatorPlan:
    name: str # e.g. "VWAP_minus_1.5_ATR" or "EMA_20_slope"
    timeframe: str
    required_indicators: List[str] # ["ATR"]
    compute_fn: Callable[[Dict[str, float], Dict[str, float], SymbolState], float]

class IndicatorRegistry:
    """
    Generic aggregator layer. Manages registration and computation of indicators.
    Supports both standard TA-Lib and dynamic "on-the-fly" derived fields.
    """
    def __init__(self):
        self.plans: Dict[str, List[IndicatorExecutionPlan]] = {}
        self.dynamic_plans: Dict[str, List[DynamicIndicatorPlan]] = {}

    def clear(self):
        """
        Clears all registered indicators.
        """
        self.plans = {}
        self.dynamic_plans = {}
        logger.info("Indicator registry cleared.")

    def register(self, name: str, timeframe: str = "1m", params: Optional[Dict[str, Any]] = None):
        """
        Register a single indicator.
        Checks if it's a dynamic derived field or a standard TA-Lib function.
        Fields NOT in either category (like 'price', 'vwap') are assumed to be base fields 
        and are skipped silently.
        """
        
        # 1. Check for Dynamic Patterns
        
        # Pattern A: {BASE}_slope (e.g. EMA_20_slope)
        slope_match = re.search(r'^(.*)_slope$', name)
        if slope_match:
            base_name = slope_match.group(1)
            # Ensure base is registered (recursive call)
            self.register(base_name, timeframe, params)
            
            def compute_slope(current: Dict[str, float], prior: Dict[str, float], state: SymbolState) -> float:
                return current.get(base_name, 0) - prior.get(base_name, 0)

            self._add_dynamic_plan(DynamicIndicatorPlan(
                name=name, timeframe=timeframe, required_indicators=[base_name], compute_fn=compute_slope
            ))
            return

        # Pattern B: {BASE}_minus_{N}_ATR (e.g. VWAP_minus_1.5_ATR)
        # Pattern C: {BASE}_plus_{N}_ATR
        band_match = re.search(r'^(.*)_(plus|minus)_([\d\.]+)_ATR(?:_(\d+))?$', name)
        if band_match:
            base_name = band_match.group(1)
            direction = band_match.group(2)
            multiplier = float(band_match.group(3))
            atr_period = band_match.group(4) or "14"
            atr_key = f"ATR_{atr_period}"
            
            # Ensure base (if it's an indicator) and ATR are registered
            if base_name.upper() in [f.upper() for f in talib.get_functions()]:
                self.register(base_name, timeframe, params)
            
            self.register("ATR", timeframe, {"timeperiod": int(atr_period)})
            
            def compute_band(current: Dict[str, float], prior: Dict[str, float], state: SymbolState) -> float:
                # Resolve base value (from indicators OR top-level snapshot)
                base_val = current.get(base_name)
                if base_val is None:
                    # Fallback to top-level fields (e.g. VWAP, price)
                    snapshot = state.get_snapshot()
                    base_val = snapshot.get(base_name.lower()) or snapshot.get("last_price")
                
                atr_val = current.get(atr_key) or current.get("ATR")
                if base_val is not None and atr_val is not None:
                    offset = multiplier * atr_val
                    return base_val + (offset if direction == "plus" else -offset)
                return 0.0

            self._add_dynamic_plan(DynamicIndicatorPlan(
                name=name, timeframe=timeframe, required_indicators=[base_name, atr_key], compute_fn=compute_band
            ))
            return

        # 2. Standard TA-Lib Check
        if name.upper() in [f.upper() for f in talib.get_functions()]:
            try:
                metric_def = {"name": name, "params": params or {}}
                new_plans = build_talib_execution_plans([metric_def])
                if timeframe not in self.plans:
                    self.plans[timeframe] = []
                self.plans[timeframe].extend(new_plans)
                logger.info(f"Registered TA-Lib indicator: {name} for {timeframe}")
            except Exception as e:
                logger.error(f"Failed to register TA-Lib indicator {name}: {e}")
        else:
            # Silently skip fields that aren't dynamic or TA-Lib indicators.
            # These are assumed to be base fields provided by the market snapshot.
            logger.debug(f"Skipping registration for base/snapshot field: {name}")

    def _add_dynamic_plan(self, plan: DynamicIndicatorPlan):
        if plan.timeframe not in self.dynamic_plans:
            self.dynamic_plans[plan.timeframe] = []
        # Avoid duplicates
        if not any(p.name == plan.name for p in self.dynamic_plans[plan.timeframe]):
            self.dynamic_plans[plan.timeframe].append(plan)
            logger.info(f"Registered Dynamic indicator: {plan.name} for {plan.timeframe}")

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

        input_map.update({
            "price": closes,
            "real": closes
        })

        timeframe_plans = self.plans.get(timeframe, [])
        results = {}
        for plan in timeframe_plans:
            try:
                input_arrays = [input_map[inp] for inp in plan.required_inputs if inp in input_map]
                min_required = plan.params.get("timeperiod", 2)
                if len(closes) <= min_required:
                    continue

                res = plan.function(*input_arrays, **plan.params)

                if isinstance(res, (list, tuple, np.ndarray)):
                    if isinstance(res, (list, tuple)):
                        for i, o_name in enumerate(plan.output_fields):
                            val = res[i][-1]
                            if not np.isnan(val):
                                results[o_name] = float(val)
                    else:
                        val = res[-1]
                        if not np.isnan(val):
                            results[plan.output_fields[0]] = float(val)
                else:
                    if not np.isnan(res):
                        results[plan.output_fields[0]] = float(res)

            except Exception as e:
                logger.error(f"Failed to compute {plan.name} for {symbol_state.symbol} on {timeframe}: {e}")

        # DYNAMIC INDICATORS (Executed on-the-fly based on registration)
        try:
            history = symbol_state.indicator_history.get(timeframe)
            prior_results = history[-1] if history else {}
            
            d_plans = self.dynamic_plans.get(timeframe, [])
            for d_plan in d_plans:
                try:
                    val = d_plan.compute_fn(results, prior_results, symbol_state)
                    results[d_plan.name] = float(val)
                except Exception as e:
                    logger.error(f"Failed to compute dynamic field {d_plan.name}: {e}")

        except Exception as e:
            logger.error(f"Dynamic indicator computation failed: {e}")

        # Update cache and history
        symbol_state.indicator_cache[timeframe] = results
        symbol_state.indicator_history[timeframe].append(results.copy())
