from pydantic import BaseModel
from typing import Optional
import uuid

class PlaybookCreate(BaseModel):
    name: str
    user_id: uuid.UUID
    original_nl_input: str
    is_active: bool = True

class PlaybookUpdate(BaseModel):
    name: Optional[str] = None
    is_active: Optional[bool] = None
