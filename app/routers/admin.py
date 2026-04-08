from fastapi import APIRouter, Depends
from sqlmodel import Session, select
from typing import List
import logging
from app.database import get_session
from app.models import User, Session as SessionModel, SessionEvent as SessionEventModel, Playbook
from app.schemas import AdminAnalyticsDashboard, AdminUserAnalytics
from app.analytics import build_admin_dashboard

from app.routers.users import get_current_manager

logger = logging.getLogger(__name__)
router = APIRouter(tags=["admin"])


def _load_dashboard(db: Session) -> AdminAnalyticsDashboard:
    users = db.exec(select(User)).all()
    playbooks = db.exec(select(Playbook)).all()
    sessions = db.exec(select(SessionModel)).all()
    events = db.exec(select(SessionEventModel)).all()
    return build_admin_dashboard(users, playbooks, sessions, events)


@router.get("/analytics", response_model=List[AdminUserAnalytics])
async def get_admin_analytics(db: Session = Depends(get_session), admin: User = Depends(get_current_manager)):
    """
    Legacy admin analytics list used by older control-center views.
    """
    dashboard = _load_dashboard(db)
    analytics: List[AdminUserAnalytics] = []

    for trader in dashboard.traders:
        analytics.append(
            AdminUserAnalytics(
                user_id=trader.user_id,
                email=trader.email,
                latest_session_id=trader.latest_session_id,
                latest_deviation_score=int(round(trader.total_deviation_events)),
                session_status=trader.latest_session_status,
                last_updated=trader.last_active_at,
            )
        )

    return analytics


@router.get("/analytics/dashboard", response_model=AdminAnalyticsDashboard)
async def get_admin_analytics_dashboard(
    db: Session = Depends(get_session),
    admin: User = Depends(get_current_manager),
):
    """
    Manager-focused analytics dashboard that surfaces discipline, cost, drift,
    and intervention abstractions across the firm.
    """
    return _load_dashboard(db)
