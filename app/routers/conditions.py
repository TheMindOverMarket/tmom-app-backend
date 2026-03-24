from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from typing import List, Optional
import uuid
import logging
from app.database import get_session
from app.models import Condition, Rule
from app.schemas import ConditionCreate, ConditionUpdate

logger = logging.getLogger(__name__)
router = APIRouter(tags=["conditions"])

@router.post("/conditions/", response_model=Condition, status_code=status.HTTP_201_CREATED)
async def create_condition(condition_in: ConditionCreate, db: Session = Depends(get_session)):
    # Validate rule exists
    rule = db.get(Rule, condition_in.rule_id)
    if not rule:
        logger.warning(f"[CONDITION] Create failed: Rule {condition_in.rule_id} not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Cannot create condition. Rule with ID {condition_in.rule_id} does not exist."
        )
        
    condition = Condition(**condition_in.dict())
    db.add(condition)
    db.commit()
    db.refresh(condition)
    logger.info(f"[CONDITION] New condition created: {condition.metric} (ID: {condition.id}) for Rule: {condition.rule_id}")
    return condition

@router.get("/conditions/", response_model=List[Condition])
async def list_conditions(rule_id: Optional[uuid.UUID] = None, db: Session = Depends(get_session)):
    statement = select(Condition)
    if rule_id:
        statement = statement.where(Condition.rule_id == rule_id)
    return db.exec(statement).all()

@router.get("/conditions/{id}", response_model=Condition)
async def get_condition(id: uuid.UUID, db: Session = Depends(get_session)):
    condition = db.get(Condition, id)
    if not condition:
        logger.warning(f"[CONDITION] Fetch failed: Condition {id} not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Condition with ID {id} was not found."
        )
    return condition

@router.patch("/conditions/{id}", response_model=Condition)
async def update_condition(id: uuid.UUID, condition_in: ConditionUpdate, db: Session = Depends(get_session)):
    condition = db.get(Condition, id)
    if not condition:
        logger.warning(f"[CONDITION] Update failed: Condition {id} not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Cannot update condition. Condition with ID {id} does not exist."
        )
    
    update_data = condition_in.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(condition, key, value)
    
    db.add(condition)
    db.commit()
    db.refresh(condition)
    logger.info(f"[CONDITION] Condition updated: {id}")
    return condition

@router.delete("/conditions/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_condition(id: uuid.UUID, db: Session = Depends(get_session)):
    condition = db.get(Condition, id)
    if not condition:
        logger.warning(f"[CONDITION] Delete failed: Condition {id} not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Cannot delete condition. Condition with ID {id} does not exist."
        )
    
    db.delete(condition)
    db.commit()
    logger.info(f"[CONDITION] Condition deleted: {id}")
    return None


@router.get("/rules/{rule_id}/conditions", response_model=List[Condition])
async def list_rule_conditions(rule_id: uuid.UUID, db: Session = Depends(get_session)):
    # Validate rule existence
    rule = db.get(Rule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
        
    statement = select(Condition).where(Condition.rule_id == rule_id)
    return db.exec(statement).all()
