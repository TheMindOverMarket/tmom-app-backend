from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from typing import List, Optional
import uuid
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

from app.database import get_session
from app.models import Session as SessionModel, SessionEvent as SessionEventModel, SessionStatus, SessionEventType
from app.schemas import SessionCreate, SessionUpdate, SessionRead, SessionEventCreate, SessionEventRead
from app.sessions import set_active_session, remove_active_session

router = APIRouter(prefix="/sessions", tags=["sessions"])

@router.post("/start", response_model=SessionRead)
def start_session(session_data: SessionCreate, db: Session = Depends(get_session)):
    try:
        # Create new session
        new_session = SessionModel(
            user_id=session_data.user_id,
            playbook_id=session_data.playbook_id,
            session_metadata=session_data.session_metadata,
            status=SessionStatus.STARTED
        )
        db.add(new_session)
        db.commit()
        db.refresh(new_session)
        
        # Mark as active globally for real-time logging
        set_active_session(new_session.playbook_id, new_session.id)
        
        return new_session
    except Exception as e:
        logger.error(f"Error starting session for playbook {session_data.playbook_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error during session start")

@router.post("/{session_id}/end", response_model=SessionRead)
def end_session(session_id: uuid.UUID, session_update: SessionUpdate, db: Session = Depends(get_session)):
    db_session = db.get(SessionModel, session_id)
    if not db_session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    db_session.end_time = datetime.now(timezone.utc)
    db_session.status = session_update.status or SessionStatus.COMPLETED
    if session_update.session_metadata:
        db_session.session_metadata = session_update.session_metadata
        
    db.add(db_session)
    db.commit()
    db.refresh(db_session)
    
    # Remove from active registry
    remove_active_session(db_session.playbook_id)
    
    return db_session

@router.get("/", response_model=List[SessionRead])
def list_sessions(user_id: Optional[uuid.UUID] = None, db: Session = Depends(get_session)):
    query = select(SessionModel)
    if user_id:
        query = query.where(SessionModel.user_id == user_id)
    return db.exec(query.order_by(SessionModel.start_time.desc())).all()

@router.get("/{session_id}", response_model=SessionRead)
def get_session_details(session_id: uuid.UUID, db: Session = Depends(get_session)):
    db_session = db.get(SessionModel, session_id)
    if not db_session:
        raise HTTPException(status_code=404, detail="Session not found")
    return db_session

@router.post("/{session_id}/events", response_model=SessionEventRead)
def add_session_event(session_id: uuid.UUID, event_data: SessionEventCreate, db: Session = Depends(get_session)):
    # Ensure session exists
    db_session = db.get(SessionModel, session_id)
    if not db_session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    new_event = SessionEventModel(
        session_id=session_id,
        type=event_data.type,
        tick=event_data.tick,
        event_data=event_data.event_data,
        event_metadata=event_data.event_metadata
    )
    db.add(new_event)
    db.commit()
    db.refresh(new_event)
    return new_event

@router.get("/{session_id}/replay", response_model=List[SessionEventRead])
def get_session_replay(session_id: uuid.UUID, db: Session = Depends(get_session)):
    query = select(SessionEventModel).where(SessionEventModel.session_id == session_id).order_by(SessionEventModel.timestamp.asc())
    return db.exec(query).all()
