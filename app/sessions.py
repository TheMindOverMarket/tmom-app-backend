import uuid
from typing import Dict, Optional
from datetime import datetime, timezone
from sqlmodel import Session
from app.database import engine
from app.models import SessionEvent, SessionEventType

# Global registry of active sessions
# Key: playbook_id (UUID), Value: session_id (UUID)
_active_sessions: Dict[uuid.UUID, uuid.UUID] = {}
# Key: playbook_id (UUID), Value: user_id (UUID)
_playbook_to_user: Dict[uuid.UUID, uuid.UUID] = {}

def set_active_session(playbook_id: uuid.UUID, session_id: uuid.UUID, user_id: uuid.UUID):
    _active_sessions[playbook_id] = session_id
    _playbook_to_user[playbook_id] = user_id

def get_active_session(playbook_id: uuid.UUID) -> Optional[uuid.UUID]:
    return _active_sessions.get(playbook_id)

def get_user_for_playbook(playbook_id: uuid.UUID) -> Optional[uuid.UUID]:
    return _playbook_to_user.get(playbook_id)

def remove_active_session(playbook_id: uuid.UUID):
    if playbook_id in _active_sessions:
        del _active_sessions[playbook_id]
    if playbook_id in _playbook_to_user:
        del _playbook_to_user[playbook_id]

def log_session_event(
    playbook_id: uuid.UUID,
    event_type: SessionEventType,
    event_data: dict,
    tick: Optional[int] = None,
    event_metadata: Optional[dict] = None
):
    session_id = get_active_session(playbook_id)
    if not session_id:
        return

    with Session(engine) as db:
        new_event = SessionEvent(
            session_id=session_id,
            type=event_type,
            tick=tick,
            event_data=event_data,
            event_metadata=event_metadata,
            timestamp=datetime.now(timezone.utc)
        )
        db.add(new_event)
        db.commit()
