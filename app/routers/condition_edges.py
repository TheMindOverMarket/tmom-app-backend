from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from typing import List, Optional
import uuid
import logging
from app.database import get_session
from app.models import ConditionEdge, Rule, Condition
from app.schemas.condition_edges import ConditionEdgeCreate, ConditionEdgeUpdate

logger = logging.getLogger(__name__)
router = APIRouter(tags=["condition-edges"])

@router.post("/condition-edges/", response_model=ConditionEdge, status_code=status.HTTP_201_CREATED)
async def create_condition_edge(edge_in: ConditionEdgeCreate, db: Session = Depends(get_session)):
    # Validate rule and conditions exist
    rule = db.get(Rule, edge_in.rule_id)
    if not rule:
        logger.warning(f"[EDGE] Create failed: Rule {edge_in.rule_id} not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Cannot create edge. Rule with ID {edge_in.rule_id} does not exist."
        )
    
    parent = db.get(Condition, edge_in.parent_condition_id)
    if not parent:
        logger.warning(f"[EDGE] Create failed: Parent condition {edge_in.parent_condition_id} not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Cannot create edge. Parent condition with ID {edge_in.parent_condition_id} does not exist."
        )
        
    child = db.get(Condition, edge_in.child_condition_id)
    if not child:
        logger.warning(f"[EDGE] Create failed: Child condition {edge_in.child_condition_id} not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Cannot create edge. Child condition with ID {edge_in.child_condition_id} does not exist."
        )
        
    edge = ConditionEdge(**edge_in.dict())
    db.add(edge)
    db.commit()
    db.refresh(edge)
    logger.info(f"[EDGE] New condition edge created (ID: {edge.id}) in Rule: {edge.rule_id}")
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
        logger.warning(f"[EDGE] Fetch failed: Edge {id} not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Condition Edge with ID {id} was not found."
        )
    return edge

@router.patch("/condition-edges/{id}", response_model=ConditionEdge)
async def update_condition_edge(id: uuid.UUID, edge_in: ConditionEdgeUpdate, db: Session = Depends(get_session)):
    edge = db.get(ConditionEdge, id)
    if not edge:
        logger.warning(f"[EDGE] Update failed: Edge {id} not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Cannot update edge. Condition Edge with ID {id} does not exist."
        )
    
    update_data = edge_in.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(edge, key, value)
    
    db.add(edge)
    db.commit()
    db.refresh(edge)
    logger.info(f"[EDGE] Condition edge updated: {id}")
    return edge

@router.delete("/condition-edges/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_condition_edge(id: uuid.UUID, db: Session = Depends(get_session)):
    edge = db.get(ConditionEdge, id)
    if not edge:
        logger.warning(f"[EDGE] Delete failed: Edge {id} not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Cannot delete edge. Condition Edge with ID {id} does not exist."
        )
    
    db.delete(edge)
    db.commit()
    logger.info(f"[EDGE] Condition edge deleted: {id}")
    return None


@router.get("/rules/{rule_id}/edges", response_model=List[ConditionEdge])
async def list_rule_edges(rule_id: uuid.UUID, db: Session = Depends(get_session)):
    # Validate rule existence
    rule = db.get(Rule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
        
    statement = select(ConditionEdge).where(ConditionEdge.rule_id == rule_id)
    return db.exec(statement).all()
