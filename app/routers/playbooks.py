from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from typing import List, Optional
import uuid
from app.database import get_session
from app.models import Playbook, User
from app.schemas.playbooks import PlaybookCreate, PlaybookUpdate, StartStreamsRequest

router = APIRouter(tags=["playbooks"])

@router.post("/playbooks/", response_model=Playbook, status_code=status.HTTP_201_CREATED)
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
        raise HTTPException(status_code=404, detail="Playbook not found")
    return playbook

@router.patch("/playbooks/{id}", response_model=Playbook)
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

@router.delete("/playbooks/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_playbook(id: uuid.UUID, db: Session = Depends(get_session)):
    playbook = db.get(Playbook, id)
    if not playbook:
        raise HTTPException(status_code=404, detail="Playbook not found")
    
    db.delete(playbook)
    db.commit()
    return None

@router.get("/users/{user_id}/playbooks", response_model=List[Playbook])
async def list_user_playbooks(user_id: uuid.UUID, db: Session = Depends(get_session)):
    # Validate user existence
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    statement = select(Playbook).where(Playbook.user_id == user_id)
    return db.exec(statement).all()

@router.post("/start_streams_creation", response_model=Playbook, status_code=status.HTTP_202_ACCEPTED)
async def start_streams_creation(request: StartStreamsRequest, db: Session = Depends(get_session)):
    # Validate playbook existence
    playbook = db.get(Playbook, request.playbook_id)
    if not playbook:
        raise HTTPException(status_code=404, detail="Playbook not found")
        
    # Validation: Ensure the user matches the playbook's owner
    if playbook.user_id != request.user_id:
        raise HTTPException(status_code=403, detail="Playbook does not belong to the specified user")
        
    # Placeholder: Future asynchronous stream creation logic goes here
    
    # Returning the Playbook simply to acknowledge receipt 
    return playbook

