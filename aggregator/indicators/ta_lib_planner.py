import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

import talib
from talib import abstract

# Set up logging
logger = logging.getLogger(__name__)

@dataclass
class IndicatorExecutionPlan:
    """
    Standardized execution plan for a TA-Lib indicator.
    """
    name: str
    function: Callable
    params: Dict[str, Any]
    required_inputs: List[str]
    output_fields: List[str]

def build_talib_execution_plans(ta_lib_metrics: List[Dict[str, Any]]) -> List[IndicatorExecutionPlan]:
    """
    Validates TA-Lib metrics from playbook context and produces validated indicator execution plans.
    
    Args:
        ta_lib_metrics: List of metric definitions from playbook.context["ta_lib_metrics"].
        
    Returns:
        A list of IndicatorExecutionPlan objects.
        
    Raises:
        ValueError: If a function name is invalid or invalid parameters are provided.
    """
    plans: List[IndicatorExecutionPlan] = []
    
    # 1. Name Validation using uppercase comparison
    available_functions = [f.upper() for f in talib.get_functions()]
    
    for metric in ta_lib_metrics:
        name = metric.get("name")
        if not name:
            logger.debug("Skipping metric entry with empty name.")
            continue
            
        if name.upper() not in available_functions:
            msg = f"Invalid TA-Lib function name: {name}"
            logger.error(msg)
            raise ValueError(msg)
            
        # 2. Abstract Function Introspection
        try:
            abs_func = abstract.Function(name)
        except Exception as e:
            msg = f"Failed to initialize TA-Lib abstract function '{name}': {e}"
            logger.error(msg)
            raise ValueError(msg)
            
        info = abs_func.info
        allowed_params = info.get("parameters", {})
        input_names_dict = info.get("input_names", {})
        output_names = info.get("output_names", [])

        # 3. Parameter Normalization
        normalized_params: Dict[str, Any] = {}
        
        # metric.timeperiod handled if present
        if metric.get("timeperiod") is not None:
            normalized_params["timeperiod"] = metric["timeperiod"]
            
        # metric.params handled if present (merging and overriding timeperiod)
        extra_params = metric.get("params")
        if isinstance(extra_params, dict):
            normalized_params.update(extra_params)
            
        # 4. Parameter Validation
        for p_key in normalized_params:
            if p_key not in allowed_params:
                msg = f"Invalid parameter '{p_key}' provided for function '{name}'"
                logger.error(msg)
                raise ValueError(msg)
        
        # 5. Required Inputs extraction (Flatten, Unique, Lowercase)
        required_inputs: List[str] = []
        for val in input_names_dict.values():
            if isinstance(val, (list, tuple)):
                required_inputs.extend([str(v).lower() for v in val])
            else:
                required_inputs.append(str(val).lower())
        
        # Unique list preserving order of first appearance
        seen = set()
        unique_inputs = []
        for inp in required_inputs:
            if inp not in seen:
                unique_inputs.append(inp)
                seen.add(inp)
        required_inputs = unique_inputs

        # 6. Output Fields Logic
        # Enforce strict downstream frontend contract:
        # - If timeperiod is present: "{name}_{timeperiod}" (e.g., "RSI_14")
        # - If timeperiod is absent: "{name}" (e.g., "MACD")
        timeperiod = metric.get("timeperiod") or normalized_params.get("timeperiod")
        base_name = f"{name}_{timeperiod}" if timeperiod is not None else name
        
        output_fields: List[str] = []
        if output_names and len(output_names) > 1:
            # Multi-output: use base_name for the first primary output, suffix others
            for i, out in enumerate(output_names):
                if i == 0:
                    output_fields.append(base_name)
                else:
                    output_fields.append(f"{base_name}_{out}")
        else:
            # Single-output or no explicit names
            output_fields = [base_name]

        # 7. Execution Plan
        plans.append(IndicatorExecutionPlan(
            name=name,
            function=abs_func,
            params=normalized_params,
            required_inputs=required_inputs,
            output_fields=output_fields
        ))
        
        logger.debug(f"Plan generated for {name}: inputs={required_inputs}, outputs={output_fields}")
        
    return plans
