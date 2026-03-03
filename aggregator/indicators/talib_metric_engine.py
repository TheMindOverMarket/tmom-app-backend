import logging
from typing import Dict, List
import numpy as np

from aggregator.indicators.symbol_state import SymbolState
from aggregator.indicators.ta_lib_planner import IndicatorExecutionPlan

logger = logging.getLogger(__name__)

class TALibMetricEngine:
    """
    Runtime engine that executes TA-Lib indicators on rolling close data.
    Phase 1: Close-only indicators supported.
    """

    def __init__(self, execution_plans: List[IndicatorExecutionPlan]) -> None:
        if not execution_plans:
            raise ValueError("TALibMetricEngine requires at least one execution plan.")

        # Validate close-only compatibility
        for plan in execution_plans:
            if plan.required_inputs != ["close"]:
                raise ValueError(
                    f"Phase 1 supports close-only indicators. "
                    f"'{plan.name}' requires inputs {plan.required_inputs}"
                )

        self.execution_plans = execution_plans
        self.symbol_states: Dict[str, SymbolState] = {}

        # Determine max lookback from plans
        lookbacks: List[int] = []
        for plan in execution_plans:
            if "timeperiod" in plan.params:
                lookbacks.append(int(plan.params["timeperiod"]))
            else:
                # Fallback lookback if no explicit timeperiod
                lookbacks.append(100)

        self.max_lookback = max(lookbacks) + 5

    def _get_symbol_state(self, symbol: str) -> SymbolState:
        if symbol not in self.symbol_states:
            self.symbol_states[symbol] = SymbolState(self.max_lookback)
        return self.symbol_states[symbol]

    def update_and_compute(self, symbol: str, close: float) -> Dict[str, float]:
        """
        Update symbol state and compute indicators.
        Returns dict of computed metric values.
        """

        state = self._get_symbol_state(symbol)
        state.update(close)

        close_history = state.get_close_array()

        if len(close_history) < self.max_lookback:
            return {}

        close_array = np.array(close_history, dtype=float)

        computed_metrics: Dict[str, float] = {}

        for plan in self.execution_plans:
            try:
                result = plan.function(close=close_array, **plan.params)

                if isinstance(result, (list, tuple, np.ndarray)):
                    latest_value = result[-1]
                else:
                    latest_value = result

                if latest_value is None or np.isnan(latest_value):
                    continue

                for field in plan.output_fields:
                    computed_metrics[field] = float(latest_value)

            except Exception as e:
                logger.debug(f"Indicator computation failed for {plan.name}: {e}")
                continue

        return computed_metrics
