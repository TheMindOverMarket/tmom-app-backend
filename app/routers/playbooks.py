from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from sqlalchemy import update as sa_update
from typing import List, Optional, Any
import uuid
import logging
from app.database import get_session
from app.models import Playbook, User
from app.schemas import PlaybookCreate, PlaybookUpdate, StartStreamsRequest, StartStreamsResponse
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
    
    # SYSTEM INVARIANT: Only one active playbook per user.
    # If this new playbook is active, deactivate all others for this user first.
    if playbook_in.is_active:
        logger.info(f"[PLAYBOOK] Creating new ACTIVE playbook for user {playbook_in.user_id}. Deactivating all others.")
        db.exec(
            sa_update(Playbook)
            .where(Playbook.user_id == playbook_in.user_id)
            .values(is_active=False)
        )
        # Flush to ensure deactivation is staged before adding the new one
        db.flush()
        
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
        
        # Atomic bulk deactivation of all other playbooks for this user
        db.exec(
            sa_update(Playbook)
            .where(Playbook.user_id == playbook.user_id)
            .where(Playbook.id != id)
            .values(is_active=False)
        )
        # Flush to ensure updates are sent to the DB before committing the entire session
        db.flush()

    for key, value in update_data.items():
        setattr(playbook, key, value)
    
    db.add(playbook)
    db.commit()
    db.refresh(playbook)
    logger.info(f"[PLAYBOOK] Playbook updated: {id} (is_active: {playbook.is_active})")
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


