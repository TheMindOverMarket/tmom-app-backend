from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlmodel import Session, select
from typing import List, Optional
import uuid
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

import app.lifecycle
from app.database import get_session
from app.models import Session as SessionModel, SessionEvent as SessionEventModel, SessionStatus, SessionEventType, Playbook, Rule, Condition
from app.session_runtime import sync_runtime_from_database
from app.schemas import SessionCreate, SessionUpdate, SessionRead, SessionEventCreate, SessionEventRead
from app.sessions import remove_active_session, log_session_event
from app.rule_engine.intelligence import trigger_session_execution, trigger_session_stop

router = APIRouter(prefix="/sessions", tags=["sessions"])

@router.post("/start", response_model=SessionRead)
async def start_session(
    session_data: SessionCreate, 
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_session)
):
    """
    Start a live session for a given playbook.
    
    This endpoint:
    1. Validates the playbook is active and has rules/conditions.
    2. Registers technical indicators.
    3. Hydrates the engine with historical data.
    4. Creates the session record.
    """
    try:
        # SYSTEM INVARIANT: Only one active session per user.
        existing_active_sessions = db.exec(
            select(SessionModel)
            .where(SessionModel.user_id == session_data.user_id)
            .where(SessionModel.status == SessionStatus.STARTED)
        ).all()
        
        if existing_active_sessions:
            logger.info(f"[SESSION][START] Found {len(existing_active_sessions)} existing live sessions for user {session_data.user_id}. Terminating them.")
            for old_session in existing_active_sessions:
                old_session.status = SessionStatus.COMPLETED
                old_session.end_time = datetime.now(timezone.utc)
                db.add(old_session)
                
                # Cleanup registry and resources
                remove_active_session(old_session.playbook_id)
                
                # Cleanup engine state for the symbol
                old_playbook = db.get(Playbook, old_session.playbook_id)
                if old_playbook and old_playbook.context:
                    symbol = old_playbook.context.get("symbol")
                    if symbol:
                        alpaca_symbol = f"{symbol}/USD" if "/" not in symbol else symbol
                        if app.lifecycle.candle_engine:
                            app.lifecycle.candle_engine.clear_symbol_state(alpaca_symbol)
            db.flush() # Ensure old sessions are updated before starting a new one

        # 1. VALIDATION PHASE (Cascading Strategy Integrity Check)
        from app.models import GenerationStatus, Rule, Condition
        
        playbook = db.get(Playbook, session_data.playbook_id)
        if not playbook:
            logger.error(f"[SESSION][VALIDATION] Playbook {session_data.playbook_id} not found")
            raise HTTPException(status_code=404, detail="Playbook not found")
            
        # A. Ownership Guard
        if playbook.user_id != session_data.user_id:
            logger.warning(f"[SESSION][VALIDATION] Ownership mismatch. User {session_data.user_id} tried to start Playbook {playbook.id}")
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to start this playbook.")

        # B. Activation Guard
        if not playbook.is_active:
             logger.warning(f"[SESSION][VALIDATION] Playbook {playbook.id} is inactive")
             raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot start a session with an inactive playbook. Please activate it first.")

        # C. Generation State Guard
        if playbook.generation_status != GenerationStatus.COMPLETED:
            logger.warning(f"[SESSION][VALIDATION] Blocking session start. Playbook {playbook.id} is in status: {playbook.generation_status}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail=f"Cannot start session. Strategy for '{playbook.name}' is still being generated. Please wait until status is COMPLETED."
            )
            
        # D. Structural Integrity Guard (Rules & Conditions)
        rules_statement = select(Rule).where(Rule.playbook_id == playbook.id).where(Rule.is_active == True)
        active_rules = db.exec(rules_statement).all()
        
        if not active_rules:
            logger.warning(f"[SESSION][VALIDATION] Blocking session start. Playbook {playbook.id} has no active rules.")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="Cannot start session. Playbook has no active rules defined. Please add/activate rules first."
            )
            
        for rule in active_rules:
            conditions_statement = select(Condition).where(Condition.rule_id == rule.id).where(Condition.is_active == True)
            active_conditions = db.exec(conditions_statement).all()
            if not active_conditions:
                 logger.warning(f"[SESSION][VALIDATION] Blocking session start. Rule {rule.name} (ID: {rule.id}) has no active conditions.")
                 raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, 
                    detail=f"Incomplete Strategy: Rule '{rule.name}' has no active conditions defined. Strategy cannot be verified."
                )
        
        logger.info(f"[SESSION][VALIDATION] Playbook {playbook.name} passed all integrity checks.")

        # 2. RECORD RECORDING PHASE
        new_session = SessionModel(
            user_id=session_data.user_id,
            playbook_id=session_data.playbook_id,
            session_metadata=session_data.session_metadata,
            status=SessionStatus.STARTED
        )
        db.add(new_session)
        db.commit()
        db.refresh(new_session)
        logger.info(f"[SESSION][START] Rebuilding runtime state after creating session {new_session.id}")
        await sync_runtime_from_database()
        
        # Log systemic start event
        log_session_event(
            playbook_id=playbook.id,
            event_type=SessionEventType.SYSTEM,
            event_data={"action": "START_SESSION", "status": "started"},
            event_metadata={"session_id": str(new_session.id)}
        )
        
        # 🚀 AUTOMATED RULE ENGINE TRIGGER
        background_tasks.add_task(trigger_session_execution, new_session.playbook_id, new_session.id, new_session.user_id)
        
        return new_session
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting session for playbook {session_data.playbook_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal Server Error during session start: {str(e)}")

@router.post("/{session_id}/end", response_model=SessionRead)
async def end_session(
    session_id: uuid.UUID, 
    session_update: SessionUpdate, 
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_session)
):
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
    
    logger.info(f"[SESSION][END] Rebuilding runtime state after ending session {session_id}")
    await sync_runtime_from_database()
    
    # 🚀 AUTOMATED RULE ENGINE SHUTDOWN
    background_tasks.add_task(trigger_session_stop, db_session.playbook_id)
    
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
        timestamp=event_data.timestamp,
        tick=event_data.tick,
        event_data=event_data.event_data,
        event_metadata=event_data.event_metadata
    )
    db.add(new_event)
    db.commit()
    db.refresh(new_event)
    return new_event

@router.get("/events/{event_id}", response_model=SessionEventRead)
def get_session_event(event_id: uuid.UUID, db: Session = Depends(get_session)):
    """Fetch a specific session event."""
    event = db.get(SessionEventModel, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Session event not found")
    return event

@router.delete("/events/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session_event(event_id: uuid.UUID, db: Session = Depends(get_session)):
    """Delete a specific session event."""
    event = db.get(SessionEventModel, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Session event not found")
    db.delete(event)
    db.commit()
    logger.info(f"[SESSION_EVENT] Event {event_id} deleted manually.")
    return None

@router.get("/{session_id}/replay", response_model=List[SessionEventRead])
def get_session_replay(session_id: uuid.UUID, db: Session = Depends(get_session)):
    query = select(SessionEventModel).where(SessionEventModel.session_id == session_id).order_by(SessionEventModel.timestamp.asc())
    return db.exec(query).all()

@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(session_id: uuid.UUID, db: Session = Depends(get_session)):
    """
    Permanently delete a session and all its associated events.
    """
    db_session = db.get(SessionModel, session_id)
    if not db_session:
        logger.warning(f"[SESSION] Delete failed: Session {session_id} not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Session with ID {session_id} not found."
        )
    
    # 1. Manual cleanup of events (to avoid FK constraints if cascade not in DB schema)
    events = db.exec(select(SessionEventModel).where(SessionEventModel.session_id == session_id)).all()
    for event in events:
        db.delete(event)
    
    # 2. Delete the session itself
    db.delete(db_session)
    db.commit()
    
    logger.info(f"[SESSION] Session {session_id} and its {len(events)} events deleted successfully.")
    return None
