from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select, func
from typing import List, Dict, Any
import uuid
from ..database import get_session
from ..models import DeviationRecord, Session as SessionModel
from pydantic import BaseModel
from datetime import datetime

router = APIRouter(prefix="/deviations", tags=["deviations"])

class DeviationSummary(BaseModel):
    session_id: uuid.UUID
    playbook_id: uuid.UUID
    total_deviation_cost: float
    total_unauthorized_gain: float
    trade_count: int
    deviation_count: int
    pending_finalization: int
    deviations_by_type: Dict[str, int]
    deviations_by_family: Dict[str, int]

@router.get("/session/{session_id}/summary", response_model=DeviationSummary)
async def get_session_deviation_summary(session_id: uuid.UUID, db: Session = Depends(get_session)):
    # 1. Verify session exists
    session_stmt = select(SessionModel).where(SessionModel.id == session_id)
    session = db.exec(session_stmt).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # 2. Get all records for this session
    stmt = select(DeviationRecord).where(DeviationRecord.session_id == session_id)
    records = db.exec(stmt).all()

    # 3. Calculate Aggregates
    summary = DeviationSummary(
        session_id=session_id,
        playbook_id=session.playbook_id,
        total_deviation_cost=sum(r.finalized_cost or r.candidate_cost or 0.0 for r in records),
        total_unauthorized_gain=sum(r.unauthorized_gain or 0.0 for r in records),
        trade_count=len(set(r.decision_id for r in records if r.decision_id)),
        deviation_count=len(records),
        pending_finalization=len([r for r in records if not r.finalized_at]),
        deviations_by_type={},
        deviations_by_family={}
    )

    for r in records:
        summary.deviations_by_type[r.deviation_type] = summary.deviations_by_type.get(r.deviation_type, 0) + 1
        summary.deviations_by_family[r.deviation_family] = summary.deviations_by_family.get(r.deviation_family, 0) + 1

    return summary

@router.get("/session/{session_id}/records", response_model=List[DeviationRecord])
async def get_session_deviation_records(session_id: uuid.UUID, db: Session = Depends(get_session)):
    stmt = select(DeviationRecord).where(DeviationRecord.session_id == session_id).order_by(DeviationRecord.detected_at.desc())
    return db.exec(stmt).all()

@router.post("/record", response_model=DeviationRecord)
async def create_deviation_record(record: DeviationRecord, db: Session = Depends(get_session)):
    db.add(record)
    db.commit()
    db.refresh(record)
    return record
