from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from typing import List, Optional, Any
import uuid
import logging
from app.database import get_session
from app.models import Playbook, User
from app.schemas import PlaybookCreate, PlaybookUpdate, StartStreamsRequest, StartStreamsResponse
import app.lifecycle
from app.routers.market_data import get_market_history
from aggregator.models import NormalizedBar
from datetime import datetime, timezone
import logging
from app.sessions import log_session_event, get_active_session
from app.models import SessionEventType

logger = logging.getLogger(__name__)

router = APIRouter(tags=["playbooks"])

@router.post("/playbooks/", response_model=Playbook, status_code=status.HTTP_201_CREATED)
async def create_playbook(playbook_in: PlaybookCreate, db: Session = Depends(get_session)):
    # Validate user exists
    user = db.get(User, playbook_in.user_id)
    if not user:
        logger.warning(f"[PLAYBOOK] Create failed: User {playbook_in.user_id} not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Cannot create playbook. User with ID {playbook_in.user_id} does not exist."
        )
        
    playbook = Playbook(**playbook_in.dict())
    db.add(playbook)
    db.commit()
    db.refresh(playbook)
    logger.info(f"[PLAYBOOK] New playbook created: {playbook.name} (ID: {playbook.id}) for User: {playbook.user_id}")
    return playbook

@router.get("/playbooks/", response_model=List[Playbook])
async def list_playbooks(user_id: Optional[uuid.UUID] = None, db: Session = Depends(get_session)):
    statement = select(Playbook)
    if user_id:
        statement = statement.where(Playbook.user_id == user_id)
    return db.exec(statement).all()

@router.get("/playbooks/{id}", response_model=Playbook)
async def get_playbook(id: uuid.UUID, db: Session = Depends(get_session)):
    playbook = db.get(Playbook, id)
    if not playbook:
        logger.warning(f"[PLAYBOOK] Fetch failed: Playbook {id} not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Playbook with ID {id} was not found."
        )
    return playbook

@router.patch("/playbooks/{id}", response_model=Playbook)
async def update_playbook(id: uuid.UUID, playbook_in: PlaybookUpdate, db: Session = Depends(get_session)):
    """
    Update a playbook's details.
    
    NOTE: If 'is_active' is set to true, all other playbooks belonging 
    to the same user will be automatically deactivated (is_active=false)
    within the same database transaction.
    """
    playbook = db.get(Playbook, id)
    if not playbook:
        logger.warning(f"[PLAYBOOK] Update failed: Playbook {id} not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Cannot update playbook. Playbook with ID {id} does not exist."
        )
    
    update_data = playbook_in.dict(exclude_unset=True)
    
    # NOTE: When a playbook is set to active (is_active=True), all other playbooks 
    # for the same user are automatically deactivated to ensure only one 
    # playbook is active at a time per user.
    if update_data.get("is_active") is True:
        logger.info(f"[PLAYBOOK] Activating playbook {id}. Auto-deactivating other playbooks for user {playbook.user_id}")
        
        # Identify other active playbooks for this user
        deactivate_statement = (
            select(Playbook)
            .where(Playbook.user_id == playbook.user_id)
            .where(Playbook.id != id)
            .where(Playbook.is_active == True)
        )
        other_active_playbooks = db.exec(deactivate_statement).all()
        
        # Deactivate them (transactional update via the same DB session)
        for other in other_active_playbooks:
            other.is_active = False
            db.add(other)

    for key, value in update_data.items():
        setattr(playbook, key, value)
    
    db.add(playbook)
    db.commit()
    db.refresh(playbook)
    logger.info(f"[PLAYBOOK] Playbook updated: {id}")
    return playbook

@router.delete("/playbooks/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_playbook(id: uuid.UUID, db: Session = Depends(get_session)):
    playbook = db.get(Playbook, id)
    if not playbook:
        logger.warning(f"[PLAYBOOK] Delete failed: Playbook {id} not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Cannot delete playbook. Playbook with ID {id} does not exist."
        )
    
    db.delete(playbook)
    db.commit()
    logger.info(f"[PLAYBOOK] Playbook deleted: {id}")
    return None


@router.get("/users/{user_id}/playbooks", response_model=List[Playbook])
async def list_user_playbooks(user_id: uuid.UUID, db: Session = Depends(get_session)):
    # Validate user existence
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    statement = select(Playbook).where(Playbook.user_id == user_id)
    return db.exec(statement).all()

@router.post("/start_streams_creation", response_model=StartStreamsResponse, status_code=status.HTTP_202_ACCEPTED)
async def start_streams_creation(request: StartStreamsRequest, db: Session = Depends(get_session)):
    # Validate playbook existence
    playbook = db.get(Playbook, request.playbook_id)
    if not playbook:
        logger.warning(f"[WORKFLOW][START_STREAMS] Failed: Playbook {request.playbook_id} not found")
        raise HTTPException(status_code=404, detail="Playbook not found")
        
    # Validation: Ensure the user matches the playbook's owner
    if playbook.user_id != request.user_id:
        logger.warning(f"[WORKFLOW][START_STREAMS] Unauthorized access attempt: User {request.user_id} tried to trigger Playbook {request.playbook_id}")
        raise HTTPException(status_code=403, detail="Playbook does not belong to the specified user")
        
    # Log the successful trigger
    logger.info(f"[WORKFLOW][START_STREAMS] Request accepted for Playbook: {playbook.id} (User: {playbook.user_id})")
    
    # Register indicators if metrics are defined
    context = playbook.context or {}
    ta_lib_metrics = context.get("ta_lib_metrics", [])

    # Clear previous indicators before re-registering
    app.lifecycle.indicator_registry.clear()

    if ta_lib_metrics:
        try:
            for metric in ta_lib_metrics:
                app.lifecycle.indicator_registry.register(
                    name=metric.get("name"),
                    timeframe=metric.get("timeframe", "1m"),
                    params=metric.get("params", {})
                )
            logger.info(f"[WORKFLOW][START_STREAMS] {len(ta_lib_metrics)} indicators registered")
            
            # 🚀 HYDRATION PHASE
            try:
                raw_symbol = context.get("symbol", "BTC")
                alpaca_symbol = f"{raw_symbol}/USD" if "/" not in raw_symbol else raw_symbol
                
                market_bars = await get_market_history(symbol=alpaca_symbol, timeframe="1Min", limit=200)
                
                if market_bars:
                    normalized_bars = [
                        NormalizedBar(
                            symbol=alpaca_symbol,  # Use exactly what the stream will use (or should it be raw_symbol?)
                            timeframe="1m",
                            open=b.open,
                            high=b.high,
                            low=b.low,
                            close=b.close,
                            volume=0.0,
                            start_time=datetime.fromtimestamp(b.time, tz=timezone.utc)
                        ) for b in market_bars
                    ]
                    
                    if app.lifecycle.candle_engine:
                        ## Depending on how the stream names the symbol (it uses BTC/USD typically)
                        app.lifecycle.candle_engine.hydrate_historical_bars(alpaca_symbol, normalized_bars)
                        logger.info(f"[WORKFLOW][START_STREAMS] Hydrated {len(normalized_bars)} historical bars for {alpaca_symbol}")
            except Exception as e:
                logger.error(f"[WORKFLOW][START_STREAMS] Failed to hydrate historical bars: {e}")
                
        except Exception as e:
            logger.error(f"[WORKFLOW][START_STREAMS] Failed to register indicators: {e}")
            raise HTTPException(status_code=400, detail=f"Invalid indicator configuration: {e}")
    else:
        logger.info("[WORKFLOW][START_STREAMS] No TA-Lib metrics defined, registry cleared")
    
    # Placeholder: Future asynchronous stream creation logic goes here
    
    # Returning a canonical success response
    res = StartStreamsResponse(
        status="accepted",
        message="Stream creation workflow initiated successfully",
        playbook=playbook
    )

    # Log to session if active
    session_id = get_active_session(playbook.id)
    if session_id:
        log_session_event(
            playbook_id=playbook.id,
            event_type=SessionEventType.SYSTEM,
            event_data={"action": "START_STREAMS", "status": "accepted"},
            event_metadata={"session_id": str(session_id)}
        )
    
    return res

