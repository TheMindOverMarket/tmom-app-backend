from pydantic import BaseModel
from typing import Optional, Dict, Any
import uuid
from app.models import Playbook

class PlaybookCreate(BaseModel):
    name: str
    user_id: uuid.UUID
    original_nl_input: str
    context: Optional[Dict[str, Any]] = None
    is_active: bool = True

class PlaybookUpdate(BaseModel):
    name: Optional[str] = None
    context: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None

class StartStreamsRequest(BaseModel):
    user_id: uuid.UUID
    playbook_id: uuid.UUID

class StartStreamsResponse(BaseModel):
    status: str
    message: str
    playbook: Playbook
