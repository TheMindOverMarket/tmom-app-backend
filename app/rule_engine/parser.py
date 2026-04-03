from typing import Dict, Any
from datetime import datetime, timezone
from app.markets import normalize_market_symbol


def _infer_symbol(raw_input_text: str) -> str:
    lowered = raw_input_text.lower()
    for asset in ("btc", "eth", "sol", "doge", "ltc", "avax"):
        if asset in lowered:
            return normalize_market_symbol(asset)
    return normalize_market_symbol(None)

def parse_user_rule(raw_input_text: str) -> Dict[str, Any]:
    """
    Parses natural language input into a structured rule representation.
    
    This function is stateless and has no dependencies on external state or databases.
    It returns a JSON-serializable dictionary representing the parsed rule.

    Args:
        raw_input_text (str): The raw text input from the user describing a rule.

    Returns:
        Dict[str, Any]: A dictionary containing:
            - text_input: The original input string.
            - rule_type: Categorization of the rule.
            - parsed_entities: Extracted trading parameters (action, symbol, etc.).
            - processed_at: ISO 8601 timestamp of when the parsing occurred.
    """
    # Mock rule parsing logic (extracted from main.py)
    # In a real scenario, this might call an LLM or a deterministic parser.
    return {
        "text_input": raw_input_text,
        "rule_type": "conditional_trade",
        "parsed_entities": {
            "action": "buy" if "buy" in raw_input_text.lower() else "sell",
            "symbol": _infer_symbol(raw_input_text),
            "condition": "price_cross"
        },
        "processed_at": datetime.now(timezone.utc).isoformat()
    }
