from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from typing import List, Optional
import uuid
from app.database import get_session
from app.models import Condition, Rule
from app.schemas.conditions import ConditionCreate, ConditionUpdate

router = APIRouter(prefix="/conditions", tags=["conditions"])

@router.post("/", response_model=Condition, status_code=status.HTTP_201_CREATED)
async def create_condition(condition_in: ConditionCreate, db: Session = Depends(get_session)):
    # Validate rule exists
    rule = db.get(Rule, condition_in.rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
        
    condition = Condition(**condition_in.dict())
    db.add(condition)
    db.commit()
    db.refresh(condition)
    return condition

@router.get("/", response_model=List[Condition])
async def list_conditions(rule_id: Optional[uuid.UUID] = None, db: Session = Depends(get_session)):
    statement = select(Condition)
    if rule_id:
        statement = statement.where(Condition.rule_id == rule_id)
    return db.exec(statement).all()

@router.get("/{id}", response_model=Condition)
async def get_condition(id: uuid.UUID, db: Session = Depends(get_session)):
    condition = db.get(Condition, id)
    if not condition:
        raise HTTPException(status_code=404, detail="Condition not found")
    return condition

@router.patch("/{id}", response_model=Condition)
async def update_condition(id: uuid.UUID, condition_in: ConditionUpdate, db: Session = Depends(get_session)):
    condition = db.get(Condition, id)
    if not condition:
        raise HTTPException(status_code=404, detail="Condition not found")
    
    update_data = condition_in.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(condition, key, value)
    
    db.add(condition)
    db.commit()
    db.refresh(condition)
    return condition

@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_condition(id: uuid.UUID, db: Session = Depends(get_session)):
    condition = db.get(Condition, id)
    if not condition:
        raise HTTPException(status_code=404, detail="Condition not found")
    
    db.delete(condition)
    db.commit()
    return None
