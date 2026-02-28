from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from typing import List
import uuid
from app.database import get_session
from app.models import User
from app.schemas.users import UserCreate, UserUpdate

router = APIRouter(tags=["users"])

@router.post("/users/", response_model=User, status_code=status.HTTP_201_CREATED)
async def create_user(user_in: UserCreate, db: Session = Depends(get_session)):
    # Check if user already exists
    existing = db.exec(select(User).where(User.email == user_in.email)).first()
    if existing:
        raise HTTPException(status_code=400, detail="User already exists")
    
    user = User(**user_in.dict())
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

@router.get("/users/", response_model=List[User])
async def list_users(db: Session = Depends(get_session)):
    return db.exec(select(User)).all()

@router.get("/users/{id}", response_model=User)
async def get_user(id: uuid.UUID, db: Session = Depends(get_session)):
    user = db.get(User, id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@router.patch("/users/{id}", response_model=User)
async def update_user(id: uuid.UUID, user_in: UserUpdate, db: Session = Depends(get_session)):
    user = db.get(User, id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    update_data = user_in.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(user, key, value)
    
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

@router.delete("/users/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(id: uuid.UUID, db: Session = Depends(get_session)):
    user = db.get(User, id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    db.delete(user)
    db.commit()
    return None
