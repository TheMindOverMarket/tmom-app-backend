from pydantic import BaseModel
from typing import Optional
import uuid

class RuleCreate(BaseModel):
    name: str
    playbook_id: uuid.UUID
    is_active: bool = True

class RuleUpdate(BaseModel):
    name: Optional[str] = None
    is_active: Optional[bool] = None
