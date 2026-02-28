from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from typing import List, Optional
import uuid
from app.database import get_session
from app.models import ConditionEdge, Rule, Condition
from app.schemas.condition_edges import ConditionEdgeCreate, ConditionEdgeUpdate

router = APIRouter(tags=["condition-edges"])

@router.post("/condition-edges/", response_model=ConditionEdge, status_code=status.HTTP_201_CREATED)
async def create_condition_edge(edge_in: ConditionEdgeCreate, db: Session = Depends(get_session)):
    # Validate rule and conditions exist
    rule = db.get(Rule, edge_in.rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    parent = db.get(Condition, edge_in.parent_condition_id)
    if not parent:
        raise HTTPException(status_code=404, detail="Parent condition not found")
        
    child = db.get(Condition, edge_in.child_condition_id)
    if not child:
        raise HTTPException(status_code=404, detail="Child condition not found")
        
    edge = ConditionEdge(**edge_in.dict())
    db.add(edge)
    db.commit()
    db.refresh(edge)
    return edge

@router.get("/condition-edges/", response_model=List[ConditionEdge])
async def list_condition_edges(rule_id: Optional[uuid.UUID] = None, db: Session = Depends(get_session)):
    statement = select(ConditionEdge)
    if rule_id:
        statement = statement.where(ConditionEdge.rule_id == rule_id)
    return db.exec(statement).all()

@router.get("/condition-edges/{id}", response_model=ConditionEdge)
async def get_condition_edge(id: uuid.UUID, db: Session = Depends(get_session)):
    edge = db.get(ConditionEdge, id)
    if not edge:
        raise HTTPException(status_code=404, detail="Condition Edge not found")
    return edge

@router.patch("/condition-edges/{id}", response_model=ConditionEdge)
async def update_condition_edge(id: uuid.UUID, edge_in: ConditionEdgeUpdate, db: Session = Depends(get_session)):
    edge = db.get(ConditionEdge, id)
    if not edge:
        raise HTTPException(status_code=404, detail="Condition Edge not found")
    
    update_data = edge_in.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(edge, key, value)
    
    db.add(edge)
    db.commit()
    db.refresh(edge)
    return edge

@router.delete("/condition-edges/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_condition_edge(id: uuid.UUID, db: Session = Depends(get_session)):
    edge = db.get(ConditionEdge, id)
    if not edge:
        raise HTTPException(status_code=404, detail="Condition Edge not found")
    
    db.delete(edge)
    db.commit()
    return None

@router.get("/rules/{rule_id}/edges", response_model=List[ConditionEdge])
async def list_rule_edges(rule_id: uuid.UUID, db: Session = Depends(get_session)):
    # Validate rule existence
    rule = db.get(Rule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
        
    statement = select(ConditionEdge).where(ConditionEdge.rule_id == rule_id)
    return db.exec(statement).all()
