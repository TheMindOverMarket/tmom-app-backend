from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from typing import List, Optional
import uuid
from app.database import get_session
from app.models import Rule, Playbook
from app.schemas.rules import RuleCreate, RuleUpdate

router = APIRouter(tags=["rules"])

@router.post("/rules/", response_model=Rule, status_code=status.HTTP_201_CREATED)
async def create_rule(rule_in: RuleCreate, db: Session = Depends(get_session)):
    # Validate playbook exists
    playbook = db.get(Playbook, rule_in.playbook_id)
    if not playbook:
        raise HTTPException(status_code=404, detail="Playbook not found")
        
    rule = Rule(**rule_in.dict())
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule

@router.get("/rules/", response_model=List[Rule])
async def list_rules(playbook_id: Optional[uuid.UUID] = None, db: Session = Depends(get_session)):
    statement = select(Rule)
    if playbook_id:
        statement = statement.where(Rule.playbook_id == playbook_id)
    return db.exec(statement).all()

@router.get("/rules/{id}", response_model=Rule)
async def get_rule(id: uuid.UUID, db: Session = Depends(get_session)):
    rule = db.get(Rule, id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    return rule

@router.patch("/rules/{id}", response_model=Rule)
async def update_rule(id: uuid.UUID, rule_in: RuleUpdate, db: Session = Depends(get_session)):
    rule = db.get(Rule, id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    update_data = rule_in.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(rule, key, value)
    
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule

@router.delete("/rules/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rule(id: uuid.UUID, db: Session = Depends(get_session)):
    rule = db.get(Rule, id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    db.delete(rule)
    db.commit()
    return None

@router.get("/playbooks/{playbook_id}/rules", response_model=List[Rule])
async def list_playbook_rules(playbook_id: uuid.UUID, db: Session = Depends(get_session)):
    # Validate playbook existence
    playbook = db.get(Playbook, playbook_id)
    if not playbook:
        raise HTTPException(status_code=404, detail="Playbook not found")
        
    statement = select(Rule).where(Rule.playbook_id == playbook_id)
    return db.exec(statement).all()
