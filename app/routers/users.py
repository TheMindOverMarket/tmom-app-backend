from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from typing import List
import uuid
import logging
from app.database import get_session
from app.models import User
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
    user = db.get(User, id)
    if not user:
        logger.warning(f"[USER] Delete failed: User {id} not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Cannot delete user. User with ID {id} does not exist."
        )
    
    db.delete(user)
    db.commit()
    logger.info(f"[USER] User deleted: {id}")
    return None

