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
    Validates TA-Lib metrics from playbook context and produces execution plans.
    
    Args:
        ta_lib_metrics: List of metric definitions from playbook.context["ta_lib_metrics"].
        
    Returns:
        A list of IndicatorExecutionPlan objects.
        
    Raises:
        ValueError: If a function name is invalid or provided parameters are not supported.
    """
    plans: List[IndicatorExecutionPlan] = []
    
    # Get all available functions for pre-validation
    available_functions = [f.upper() for f in talib.get_functions()]
    
    for metric in ta_lib_metrics:
        name = metric.get("name")
        if not name:
            logger.warning("Found metric entry without a name. Skipping.")
            continue
            
        # 1. Validate "name" exists in TA-Lib
        if name.upper() not in available_functions:
            logger.error(f"TA-Lib function '{name}' does not exist.")
            raise ValueError(f"TA-Lib function '{name}' does not exist.")
            
        # 2. Use talib.abstract.Function(name) to introspect
        try:
            abs_func = abstract.Function(name)
        except Exception as e:
            logger.error(f"Failed to initialize TA-Lib abstract function '{name}': {e}")
            raise ValueError(f"Failed to initialize TA-Lib abstract function '{name}': {e}")
            
        info = abs_func.info
        
        # 3. Normalize params
        # a) If metric has "timeperiod", include it in params.
        # b) If metric has "params", merge dict into params.
        # c) If both exist, merge with explicit params taking priority.
        normalized_params: Dict[str, Any] = {}
        
        if "timeperiod" in metric and metric["timeperiod"] is not None:
            normalized_params["timeperiod"] = metric["timeperiod"]
            
        extra_params = metric.get("params")
        if isinstance(extra_params, dict):
            normalized_params.update(extra_params)
            
        # 4. Validate that provided params are valid for that function
        allowed_params = info.get("parameters", {})
        for p_name in normalized_params:
            if p_name not in allowed_params:
                logger.error(f"Invalid parameter '{p_name}' for TA-Lib function '{name}'.")
                raise ValueError(f"Invalid parameter '{p_name}' for TA-Lib function '{name}'.")
        
        # 5. Determine required_inputs from abstract API
        # input_names is typically an OrderedDict like {'price': 'close'} or {'high': 'high', ...}
        # We need the values (the column names).
        required_inputs: List[str] = []
        input_names_dict = info.get("input_names", {})
        for val in input_names_dict.values():
            if isinstance(val, (list, tuple)):
                required_inputs.extend([str(v) for v in val])
            else:
                required_inputs.append(str(val))
        
        # Ensure unique inputs
        required_inputs = sorted(list(set(required_inputs)))
        
        # 6. Determine output field names
        output_names = info.get("output_names", [])
        
        if len(output_names) == 1:
            # For single-output functions: output_fields = [f"{name}_{primary_param_signature}"]
            # Generate signature from normalized_params values.
            # If no parameters provided/applicable, use just the name or default timeperiod.
            if normalized_params:
                # Use sorted keys for deterministic signature
                sig_values = [str(normalized_params[k]) for k in sorted(normalized_params.keys())]
                sig = "_".join(sig_values)
                output_fields = [f"{name}_{sig}"]
            else:
                # If no params provided, check if function has a default timeperiod to include
                default_timeperiod = allowed_params.get("timeperiod")
                if default_timeperiod is not None:
                    output_fields = [f"{name}_{default_timeperiod}"]
                else:
                    output_fields = [f"{name}"]
        else:
            # For multi-output functions: output_fields = list of abstract function output names
            output_fields = list(output_names)
            
        # 7. Add to plans
        plans.append(IndicatorExecutionPlan(
            name=name,
            function=abs_func,
            params=normalized_params,
            required_inputs=required_inputs,
            output_fields=output_fields
        ))
        
        logger.debug(f"Planned indicator {name}: inputs={required_inputs}, outputs={output_fields}")
        
    return plans
