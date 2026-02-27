from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from typing import List, Optional
import uuid
from app.database import get_session
from app.models import Playbook, User
from app.schemas.playbooks import PlaybookCreate, PlaybookUpdate

router = APIRouter(prefix="/playbooks", tags=["playbooks"])

@router.post("/", response_model=Playbook, status_code=status.HTTP_201_CREATED)
async def create_playbook(playbook_in: PlaybookCreate, db: Session = Depends(get_session)):
    # Validate user exists
    user = db.get(User, playbook_in.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    playbook = Playbook(**playbook_in.dict())
    db.add(playbook)
    db.commit()
    db.refresh(playbook)
    return playbook

@router.get("/", response_model=List[Playbook])
async def list_playbooks(user_id: Optional[uuid.UUID] = None, db: Session = Depends(get_session)):
    statement = select(Playbook)
    if user_id:
        statement = statement.where(Playbook.user_id == user_id)
    return db.exec(statement).all()

@router.get("/{id}", response_model=Playbook)
async def get_playbook(id: uuid.UUID, db: Session = Depends(get_session)):
    playbook = db.get(Playbook, id)
    if not playbook:
        raise HTTPException(status_code=404, detail="Playbook not found")
    return playbook

@router.patch("/{id}", response_model=Playbook)
async def update_playbook(id: uuid.UUID, playbook_in: PlaybookUpdate, db: Session = Depends(get_session)):
    playbook = db.get(Playbook, id)
    if not playbook:
        raise HTTPException(status_code=404, detail="Playbook not found")
    
    update_data = playbook_in.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(playbook, key, value)
    
    db.add(playbook)
    db.commit()
    db.refresh(playbook)
    return playbook

@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_playbook(id: uuid.UUID, db: Session = Depends(get_session)):
    playbook = db.get(Playbook, id)
    if not playbook:
        raise HTTPException(status_code=404, detail="Playbook not found")
    
    db.delete(playbook)
    db.commit()
    return None
