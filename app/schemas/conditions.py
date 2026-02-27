from pydantic import BaseModel
from typing import Optional
import uuid

class ConditionCreate(BaseModel):
    rule_id: uuid.UUID
    metric: str
    comparator: str
    value: str
    is_active: bool = True

class ConditionUpdate(BaseModel):
    metric: Optional[str] = None
    comparator: Optional[str] = None
    value: Optional[str] = None
    is_active: Optional[bool] = None
