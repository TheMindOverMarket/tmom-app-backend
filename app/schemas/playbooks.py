from pydantic import BaseModel, model_validator
from typing import Optional, Dict, Any
import uuid
from app.models import Playbook


HARDCODED_PROMPT = """
I’m using BTC.

1. Setup Logic (Deterministic Inputs)

Derived State:
	•	Session VWAP (UTC daily reset)
	•	20-period EMA
	•	14-period ATR
	•	Rolling volatility regime
	•	Daily realized PnL

⸻

Long Setup

Conditions must ALL be true:
	1.	Price < VWAP − 1.5 × ATR
	2.	EMA slope > 0
	3.	5-min close back above prior candle high
	4.	Not within 10 minutes of previous stop

⸻

Short Setup
	1.	Price > VWAP + 1.5 × ATR
	2.	EMA slope < 0
	3.	5-min close below prior candle low
	4.	Not within 10 minutes of previous stop

⸻

2. Entry Rules
	•	Market order at next candle open.
	•	Max 1 position at a time.
	•	No pyramiding.
	•	No flipping within 5 minutes.

⸻

3. Risk Model

Stop: 1 ATR
Target: 2 ATR
Trailing stop activates at +1R
Max daily loss: 3R
Max 5 trades per UTC day
Position size: 1% account risk per trade

⸻

4. Meta Discipline Rules (Where TMOM Shines)

Hard Constraints:
	•	Block trade if daily loss ≥ 3R
	•	Block if > 5 trades
	•	Block if position size > 1% risk

Soft Guardrails:
	•	Warn if trade taken within 3 minutes of prior close
	•	Warn if volatility > 95th percentile
	•	Require justification if third consecutive loss

Cooldown:
	•	10 minutes after stop loss
	•	30 minutes after 2 consecutive losses
"""

class PlaybookCreate(BaseModel):
    name: str
    user_id: uuid.UUID = uuid.UUID("1d4d88c7-bcd1-4813-8f34-59c9776e5b3f")
    original_nl_input: str
    context: Optional[Dict[str, Any]] = None
    is_active: bool = True

    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "Sample BTC Ruleset",
                "user_id": "1d4d88c7-bcd1-4813-8f34-59c9776e5b3f",
                "original_nl_input": HARDCODED_PROMPT,
                "context": {
                    "description": "Auto-generated sample playbook from utility endpoint",
                    "symbol": "BTC/USD"
                },
                "is_active": True
            }
        }
    }

    @model_validator(mode="before")
    @classmethod
    def cast_context_floats(cls, values: Any) -> Any:
        def parse_floats(data: Any) -> Any:
            if isinstance(data, dict):
                return {k: parse_floats(v) for k, v in data.items()}
            elif isinstance(data, list):
                return [parse_floats(v) for v in data]
            elif isinstance(data, str):
                try:
                    return float(data)
                except ValueError:
                    return data
            return data
            
        if isinstance(values, dict) and values.get("context"):
            values["context"] = parse_floats(values["context"])
        return values

class PlaybookUpdate(BaseModel):
    name: Optional[str] = None
    original_nl_input: Optional[str] = None
    context: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None

    @model_validator(mode="before")
    @classmethod
    def cast_context_floats(cls, values: Any) -> Any:
        def parse_floats(data: Any) -> Any:
            if isinstance(data, dict):
                return {k: parse_floats(v) for k, v in data.items()}
            elif isinstance(data, list):
                return [parse_floats(v) for v in data]
            elif isinstance(data, str):
                try:
                    return float(data)
                except ValueError:
                    return data
            return data
            
        if isinstance(values, dict) and values.get("context"):
            values["context"] = parse_floats(values["context"])
        return values


class StartStreamsRequest(BaseModel):
    user_id: uuid.UUID = uuid.UUID("1d4d88c7-bcd1-4813-8f34-59c9776e5b3f")
    playbook_id: uuid.UUID


class StartStreamsResponse(BaseModel):
    status: str
    message: str
    playbook: Playbook
