from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from sqlmodel import Session, select
from typing import List
import uuid
import logging
import jwt
from passlib.context import CryptContext
from app.database import get_session
from app.models import (
    User, Playbook, Rule, Condition, ConditionEdge, 
    Session as SessionModel, SessionEvent as SessionEventModel
)
from app.schemas import UserCreate, UserUpdate, UserLogin
from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(tags=["users"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password, hashed_password):
    if not hashed_password: return False
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict):
    return jwt.encode(data, settings.jwt_secret, algorithm="HS256")

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
    
    user_data = user_in.dict(exclude={"password"})
    hashed_password = get_password_hash(user_in.password)
    user = User(**user_data, hashed_password=hashed_password)
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.info(f"[USER] New user created: {user.email} (ID: {user.id})")
    return user

    return user

@router.post("/users/login", response_model=User)
async def login_user(login_data: UserLogin, response: Response, db: Session = Depends(get_session)):
    user = db.exec(select(User).where(User.email == login_data.email)).first()
    if not user or not verify_password(login_data.password, user.hashed_password):
        logger.warning(f"[USER] Login failed: Invalid credentials for {login_data.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Invalid email or password."
        )
    
    token = create_access_token({"sub": str(user.id)})
    response.set_cookie(key="access_token", value=token, httponly=True, samesite="lax", max_age=86400 * 7)
    logger.info(f"[USER] User logged in: {user.email}")
    return user

@router.post("/users/logout")
async def logout_user(response: Response):
    response.delete_cookie(key="access_token")
    return {"status": "Logged out"}

@router.get("/users/me", response_model=User)
async def get_current_user(request: Request, db: Session = Depends(get_session)):
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    
    user = db.get(User, uuid.UUID(user_id))
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
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
