from pydantic import BaseModel, model_validator
from typing import Optional, Dict, Any
import uuid
from app.models import Playbook

class PlaybookCreate(BaseModel):
    name: str
    user_id: uuid.UUID = uuid.UUID("1d4d88c7-bcd1-4813-8f34-59c9776e5b3f")
    original_nl_input: str
    context: Optional[Dict[str, Any]] = None
    is_active: bool = True

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
