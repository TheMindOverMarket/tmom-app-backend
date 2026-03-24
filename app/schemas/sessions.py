import uuid
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel
from app.models import SessionStatus, SessionEventType

class SessionCreate(BaseModel):
    user_id: uuid.UUID
    playbook_id: uuid.UUID
    session_metadata: Optional[Dict[str, Any]] = None

class SessionUpdate(BaseModel):
    status: Optional[SessionStatus] = None
    session_metadata: Optional[Dict[str, Any]] = None

class SessionRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    playbook_id: uuid.UUID
    start_time: datetime
    end_time: Optional[datetime] = None
    status: SessionStatus
    session_metadata: Optional[Dict[str, Any]] = None
    created_at: datetime

    class Config:
        from_attributes = True

class SessionEventCreate(BaseModel):
    session_id: uuid.UUID
    type: SessionEventType
    tick: Optional[int] = None
    event_data: Dict[str, Any]
    event_metadata: Optional[Dict[str, Any]] = None

class SessionEventRead(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    type: SessionEventType
    timestamp: datetime
    tick: Optional[int] = None
    event_data: Dict[str, Any]
    event_metadata: Optional[Dict[str, Any]] = None
    created_at: datetime

    class Config:
        from_attributes = True
