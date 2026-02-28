from pydantic import BaseModel
from typing import Optional, Dict, Any
import uuid
from app.models import Playbook

class PlaybookCreate(BaseModel):
    name: str
    user_id: uuid.UUID = uuid.UUID("1d4d88c7-bcd1-4813-8f34-59c9776e5b3f")
    original_nl_input: str
    context: Optional[Dict[str, Any]] = None
    is_active: bool = True

class PlaybookUpdate(BaseModel):
    name: Optional[str] = None
    original_nl_input: Optional[str] = None
    context: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class StartStreamsRequest(BaseModel):
    user_id: uuid.UUID = uuid.UUID("1d4d88c7-bcd1-4813-8f34-59c9776e5b3f")
    playbook_id: uuid.UUID


class StartStreamsResponse(BaseModel):
    status: str
    message: str
    playbook: Playbook
