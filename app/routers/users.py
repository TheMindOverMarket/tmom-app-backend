from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from typing import List
import uuid
import logging
from app.database import get_session
from app.models import (
    User, Playbook, Rule, Condition, ConditionEdge, 
    Session as SessionModel, SessionEvent as SessionEventModel
)
from app.schemas import UserCreate, UserUpdate

logger = logging.getLogger(__name__)
router = APIRouter(tags=["users"])

@router.post("/users/", response_model=User, status_code=status.HTTP_201_CREATED)
async def create_user(user_in: UserCreate, db: Session = Depends(get_session)):
    # Check if user already exists
    existing = db.exec(select(User).where(User.email == user_in.email)).first()
    if existing:
        logger.warning(f"[USER] Create failed: Email {user_in.email} already registered")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="A user with this email address already exists. Please use a unique email."
        )
    
    user = User(**user_in.dict())
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.info(f"[USER] New user created: {user.email} (ID: {user.id})")
    return user

@router.get("/users/", response_model=List[User])
async def list_users(db: Session = Depends(get_session)):
    return db.exec(select(User)).all()

@router.get("/users/{id}", response_model=User)
async def get_user(id: uuid.UUID, db: Session = Depends(get_session)):
    user = db.get(User, id)
    if not user:
        logger.warning(f"[USER] Fetch failed: User {id} not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"User with ID {id} was not found in our records."
        )
    return user

@router.patch("/users/{id}", response_model=User)
async def update_user(id: uuid.UUID, user_in: UserUpdate, db: Session = Depends(get_session)):
    user = db.get(User, id)
    if not user:
        logger.warning(f"[USER] Update failed: User {id} not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Cannot update user. User with ID {id} does not exist."
        )
    
    update_data = user_in.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(user, key, value)
    
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.info(f"[USER] User updated: {id}")
    return user

@router.delete("/users/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(id: uuid.UUID, db: Session = Depends(get_session)):
    """
    Cascading Delete Invariant:
    User -> Playbooks -> [Sessions, Rules] -> [Events, Conditions, Edges]
    """
    user = db.get(User, id)
    if not user:
        logger.warning(f"[USER] Delete failed: User {id} not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Cannot delete user. User with ID {id} does not exist."
        )
    
    logger.info(f"[USER][DELETE] Starting cascading cleanup for User: {id}")

    # 1. Get all Playbooks for this user
    playbooks = db.exec(select(Playbook).where(Playbook.user_id == id)).all()
    
    for playbook in playbooks:
        # A. Cleanup Sessions & Events for this playbook
        sessions = db.exec(select(SessionModel).where(SessionModel.playbook_id == playbook.id)).all()
        for session in sessions:
            events = db.exec(select(SessionEventModel).where(SessionEventModel.session_id == session.id)).all()
            for event in events:
                db.delete(event)
            db.delete(session)
            
        # B. Cleanup Rules, Conditions & Edges for this playbook
        rules = db.exec(select(Rule).where(Rule.playbook_id == playbook.id)).all()
        for rule in rules:
            edges = db.exec(select(ConditionEdge).where(ConditionEdge.rule_id == rule.id)).all()
            for edge in edges:
                db.delete(edge)
            conditions = db.exec(select(Condition).where(Condition.rule_id == rule.id)).all()
            for condition in conditions:
                db.delete(condition)
            db.delete(rule)
        
        # C. Delete the playbook itself
        db.delete(playbook)

    # 2. Finally delete the user
    db.delete(user)
    db.commit()
    
    logger.info(f"[USER][DELETE] User {id} and all their playbooks/logs permanently removed.")
    return None
