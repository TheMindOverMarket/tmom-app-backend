from pydantic import BaseModel
from typing import Optional, Dict, Any
import uuid

class RuleCreate(BaseModel):
    name: str
    playbook_id: uuid.UUID
    is_active: bool = True

class RuleUpdate(BaseModel):
    name: Optional[str] = None
    is_active: Optional[bool] = None

class RuleIngestRequest(BaseModel):
    rule_nl: str
    user_id: Optional[str] = "default_user"
    playbook_id: Optional[str] = "default_playbook"

class RuleIngestResponse(BaseModel):
    ruleId: str
    status: str
