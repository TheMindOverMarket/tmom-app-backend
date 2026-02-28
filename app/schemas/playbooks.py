from pydantic import BaseModel
from typing import Optional, Dict, Any
import uuid

class PlaybookCreate(BaseModel):
    name: str
    user_id: uuid.UUID
    original_nl_input: str
    market_data_fields: Optional[Dict[str, Any]] = None
    is_active: bool = True

class PlaybookUpdate(BaseModel):
    name: Optional[str] = None
    market_data_fields: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None
