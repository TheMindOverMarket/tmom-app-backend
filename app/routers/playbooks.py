from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select
from sqlalchemy import update as sa_update
from sqlalchemy.orm.attributes import flag_modified
from typing import List, Optional, Any
import uuid
import logging
import httpx
from app.database import get_session
from app.config import settings
from app.models import (
    Playbook, User, Rule, Condition, ConditionEdge, 
    Session as SessionModel, SessionEvent as SessionEventModel,
    SessionEventType, GenerationStatus
)
from app.schemas import PlaybookCreate, PlaybookUpdate, PlaybookIngest, PlaybookChatTurn
from app.rule_engine.intelligence import analyze_playbook_execution
from app.markets import sync_playbook_market_state

logger = logging.getLogger(__name__)

router = APIRouter(tags=["playbooks"])


def _hydrate_playbook_market_fields(playbook: Playbook) -> Playbook:
    """
    Temporary compatibility shim:
    older playbook rows may still be missing symbol/market while the migration
    rollout settles. Normalize them in-memory so reads do not 500.
    """
    symbol, market, context = sync_playbook_market_state(
        symbol=playbook.symbol,
        market=playbook.market,
        context=playbook.context,
    )
    playbook.symbol = symbol
    playbook.market = market
    playbook.context = context
    return playbook

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
    
    # SYSTEM INVARIANT: Only one active playbook per user.
    if playbook_in.is_active:
        logger.info(f"[PLAYBOOK] Creating new ACTIVE playbook for user {playbook_in.user_id}. Deactivating all others.")
        db.exec(
            sa_update(Playbook)
            .where(Playbook.user_id == playbook_in.user_id)
            .values(is_active=False)
        )
        db.flush()
        
    playbook_payload = playbook_in.model_dump()
    playbook = Playbook(**playbook_payload)
    db.add(playbook)
    db.commit()
    db.refresh(playbook)
    logger.info(f"[PLAYBOOK] New playbook created: {playbook.name} (ID: {playbook.id}) for User: {playbook.user_id}")
    return playbook

@router.post("/playbooks/ingest", response_model=Playbook, status_code=status.HTTP_201_CREATED)
async def ingest_playbook(
    playbook_in: PlaybookIngest, 
    background_tasks: BackgroundTasks, 
    db: Session = Depends(get_session)
):
    """
    INGESTION LIFECYCLE:
    1. Create a Playbook record with generation_status="PENDING".
    2. Atomic Invariant: Maintain only one active playbook per user.
    3. Lifecycle Trigger: Start LLM extraction in the background.
    """
    user = db.get(User, playbook_in.user_id)
    if not user:
        logger.warning(f"[PLAYBOOK][INGEST] User {playbook_in.user_id} not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Cannot ingest. User {playbook_in.user_id} not found."
        )

    logger.info(f"[PLAYBOOK][INGEST] Creating new PENDING playbook for User: {playbook_in.user_id}")
    db.exec(
        sa_update(Playbook)
        .where(Playbook.user_id == playbook_in.user_id)
        .values(is_active=False)
    )
    db.flush()

    playbook_payload = playbook_in.model_dump()
    playbook_payload["context"] = {
        "symbol": playbook_payload["symbol"],
        "market": playbook_payload["market"],
    }
    playbook_payload["chat_history"] = [
        {"role": "user", "content": playbook_in.original_nl_input}
    ]
    playbook_payload["is_active"] = True
    playbook_payload["generation_status"] = GenerationStatus.PENDING
    playbook = Playbook(**playbook_payload)
    db.add(playbook)
    db.commit()
    db.refresh(playbook)
    
    background_tasks.add_task(analyze_playbook_execution, playbook.id)
    logger.info(f"[PLAYBOOK][INGESTED] ID: {playbook.id} - Extraction Triggered")
    return playbook

@router.post("/playbooks/{id}/chat", response_model=Playbook)
async def chat_playbook(
    id: uuid.UUID,
    turn: PlaybookChatTurn,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_session)
):
    """
    Continues an incomplete playbook evaluation by appending a user response to the chat history.
    """
    playbook = db.get(Playbook, id)
    if not playbook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Playbook with ID {id} was not found."
        )

    history = playbook.chat_history or []
    history.append({"role": "user", "content": turn.message})
    
    playbook.chat_history = list(history)
    flag_modified(playbook, "chat_history")
    playbook.generation_status = GenerationStatus.PENDING
    
    db.add(playbook)
    db.commit()
    db.refresh(playbook)
    
    background_tasks.add_task(analyze_playbook_execution, playbook.id)
    logger.info(f"[PLAYBOOK][CHAT] ID: {playbook.id} - Extraction Re-Triggered")
    return _hydrate_playbook_market_fields(playbook)

@router.get("/playbooks/{id}/stream")
async def stream_playbook(id: uuid.UUID):
    """
    SSE Proxy: Streams the AI response from the Rule Engine.
    """
    # Note: We use the Rule Engine's streaming endpoint
    target_url = f"{settings.rule_engine_base_url}/api/rules/stream?playbook_id={id}"
    
    async def event_generator():
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream("GET", target_url) as response:
                async for chunk in response.aiter_bytes():
                    yield chunk

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.post("/playbooks/preview")
async def preview_playbook(turn: dict):
    """
    Stateless Proxy: Forwards chat_history to Rule Engine for non-persisted logic preview.
    """
    target_url = f"{settings.rule_engine_base_url}/api/rules/preview"
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(target_url, json=turn)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"[PLAYBOOK][PREVIEW][ERROR] Failed to reach Rule Engine: {str(e)}")
            raise HTTPException(status_code=500, detail="Rule Engine preview failed.")

@router.post("/playbooks/stream-preview")
async def stream_preview_playbook(turn: dict):
    """
    Stateless SSE Proxy: Streams tokens from Rule Engine without playbook_id.
    """
    target_url = f"{settings.rule_engine_base_url}/api/rules/stream"
    
    async def event_generator():
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream("POST", target_url, json=turn) as response:
                async for chunk in response.aiter_bytes():
                    yield chunk

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.get("/playbooks/", response_model=List[Playbook])
async def list_playbooks(user_id: Optional[uuid.UUID] = None, db: Session = Depends(get_session)):
    statement = select(Playbook)
    if user_id:
        statement = statement.where(Playbook.user_id == user_id)
    playbooks = db.exec(statement).all()
    return [_hydrate_playbook_market_fields(playbook) for playbook in playbooks]

@router.get("/playbooks/{id}", response_model=Playbook)
async def get_playbook(id: uuid.UUID, db: Session = Depends(get_session)):
    playbook = db.get(Playbook, id)
    if not playbook:
        logger.warning(f"[PLAYBOOK] Fetch failed: Playbook {id} not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Playbook with ID {id} was not found."
        )
    return _hydrate_playbook_market_fields(playbook)

@router.patch("/playbooks/{id}", response_model=Playbook)
async def update_playbook(id: uuid.UUID, playbook_in: PlaybookUpdate, db: Session = Depends(get_session)):
    playbook = db.get(Playbook, id)
    if not playbook:
        logger.warning(f"[PLAYBOOK] Update failed: Playbook {id} not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Cannot update playbook. Playbook with ID {id} does not exist."
        )
    
    update_data = playbook_in.model_dump(exclude_unset=True)
    if any(key in update_data for key in ("symbol", "market", "context")):
        symbol, market, context = sync_playbook_market_state(
            symbol=update_data.get("symbol", playbook.symbol),
            market=update_data.get("market", playbook.market),
            context=update_data.get("context", playbook.context),
        )
        update_data["symbol"] = symbol
        update_data["market"] = market
        update_data["context"] = context
    if update_data.get("is_active") is True:
        logger.info(f"[PLAYBOOK] Activating playbook {id}. Auto-deactivating other playbooks for user {playbook.user_id}")
        db.exec(
            sa_update(Playbook)
            .where(Playbook.user_id == playbook.user_id)
            .where(Playbook.id != id)
            .values(is_active=False)
        )
        db.flush()

    for key, value in update_data.items():
        setattr(playbook, key, value)
        if key in ("chat_history", "context", "session_metadata"):
            flag_modified(playbook, key)
    
    db.add(playbook)
    db.commit()
    db.refresh(playbook)
    logger.info(f"[PLAYBOOK] Playbook updated: {id} (is_active: {playbook.is_active})")
    return playbook

def _delete_playbook_cascading(db: Session, playbook_id: uuid.UUID):
    """
    Permanently removes a playbook. 
    Foreign key constraints (ON DELETE CASCADE) handle the cleanup of:
    - Rules -> Conditions -> Edges
    - Sessions -> SessionEvents
    """
    playbook = db.get(Playbook, playbook_id)
    if playbook:
        sessions = db.exec(select(SessionModel).where(SessionModel.playbook_id == playbook_id)).all()
        for session in sessions:
            events = db.exec(select(SessionEventModel).where(SessionEventModel.session_id == session.id)).all()
            for event in events:
                db.delete(event)
            db.delete(session)

        rules = db.exec(select(Rule).where(Rule.playbook_id == playbook_id)).all()
        for rule in rules:
            edges = db.exec(select(ConditionEdge).where(ConditionEdge.rule_id == rule.id)).all()
            for edge in edges:
                db.delete(edge)

            conditions = db.exec(select(Condition).where(Condition.rule_id == rule.id)).all()
            for condition in conditions:
                db.delete(condition)

            db.delete(rule)

        db.delete(playbook)

@router.delete("/playbooks/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_playbook(id: uuid.UUID, db: Session = Depends(get_session)):
    """
    Permanently removes a playbook and all its associated logic/sessions.
    """
    playbook = db.get(Playbook, id)
    if not playbook:
        logger.warning(f"[PLAYBOOK] Delete failed: Playbook {id} not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Cannot delete playbook. Playbook with ID {id} does not exist."
        )
    
    logger.info(f"[PLAYBOOK][DELETE] Starting cascading cleanup for Playbook: {id}")
    _delete_playbook_cascading(db, id)
    db.commit()
    logger.info(f"[PLAYBOOK][DELETE] Playbook {id} and all associated data permanently removed.")
    return None

@router.delete("/users/{user_id}/playbooks", status_code=status.HTTP_204_NO_CONTENT)
async def delete_all_user_playbooks(user_id: uuid.UUID, db: Session = Depends(get_session)):
    """
    Deletes all playbooks for a specific user.
    """
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    playbooks = db.exec(select(Playbook).where(Playbook.user_id == user_id)).all()
    logger.info(f"[PLAYBOOK][DELETE_ALL] Deleting {len(playbooks)} playbooks for user {user_id}")
    
    for pb in playbooks:
        _delete_playbook_cascading(db, pb.id)
        
    db.commit()
    logger.info(f"[PLAYBOOK][DELETE_ALL] All playbooks for user {user_id} have been removed.")
    return None

@router.get("/users/{user_id}/playbooks", response_model=List[Playbook])
async def list_user_playbooks(user_id: uuid.UUID, db: Session = Depends(get_session)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    statement = select(Playbook).where(Playbook.user_id == user_id)
    playbooks = db.exec(statement).all()
    return [_hydrate_playbook_market_fields(playbook) for playbook in playbooks]
