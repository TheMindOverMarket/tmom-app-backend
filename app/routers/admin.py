from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select, desc
from typing import List
import uuid
import logging
from app.database import get_session
from app.models import User, Session as SessionModel, SessionEvent as SessionEventModel, UserRole
from app.schemas import AdminUserAnalytics

from app.routers.users import get_current_manager

logger = logging.getLogger(__name__)
router = APIRouter(tags=["admin"])

@router.get("/analytics", response_model=List[AdminUserAnalytics])
async def get_admin_analytics(db: Session = Depends(get_session), admin: User = Depends(get_current_manager)):
    """
    Fetch session analytics for all users.
    Returns the latest session and its final deviation score for each user.
    """
    users = db.exec(select(User)).all()
    analytics = []
    
    for user in users:
        # Find latest session for this user
        latest_session = db.exec(
            select(SessionModel)
            .where(SessionModel.user_id == user.id)
            .order_by(desc(SessionModel.start_time))
        ).first()
        
        score = 0
        status = None
        last_updated = None
        session_id = None
        
        if latest_session:
            session_id = latest_session.id
            status = latest_session.status
            last_updated = latest_session.start_time
            
            # Find latest event to get the current accumulated_deviation
            latest_event = db.exec(
                select(SessionEventModel)
                .where(SessionEventModel.session_id == latest_session.id)
                .order_by(desc(SessionEventModel.timestamp))
            ).first()
            
            if latest_event and latest_event.event_data:
                score = latest_event.event_data.get("accumulated_deviation", 0)
                if latest_event.timestamp:
                    last_updated = latest_event.timestamp
        
        analytics.append(AdminUserAnalytics(
            user_id=user.id,
            email=user.email,
            latest_session_id=session_id,
            latest_deviation_score=score,
            session_status=status,
            last_updated=last_updated
        ))
    
    return analytics
