from datetime import datetime, timedelta, timezone
import uuid

from sqlmodel import Session

from app.main import app
from app.models import Playbook, Session as SessionModel, SessionEvent, SessionEventType, SessionStatus, User, UserRole
from app.routers.users import get_current_manager


async def _manager_override() -> User:
    return User(
        id=uuid.uuid4(),
        email="manager@example.com",
        first_name="Manager",
        last_name="User",
        role=UserRole.MANAGER,
        hashed_password="hashed",
    )


def test_admin_dashboard_aggregates_platform_risk(client, db_session: Session):
    app.dependency_overrides[get_current_manager] = _manager_override
    try:
        now = datetime.now(timezone.utc)

        trader_a = User(
            email="trader-a@example.com",
            first_name="Trader",
            last_name="Alpha",
            role=UserRole.TRADER,
            hashed_password="hashed",
        )
        trader_b = User(
            email="trader-b@example.com",
            first_name="Trader",
            last_name="Beta",
            role=UserRole.TRADER,
            hashed_password="hashed",
        )
        db_session.add(trader_a)
        db_session.add(trader_b)
        db_session.commit()
        db_session.refresh(trader_a)
        db_session.refresh(trader_b)

        playbook_a = Playbook(
            user_id=trader_a.id,
            name="Opening Drive",
            symbol="ETH/USD",
            market="ETH/USD",
            original_nl_input="Wait for breakout confirmation and respect size.",
        )
        playbook_b = Playbook(
            user_id=trader_b.id,
            name="Trend Follow",
            symbol="BTC/USD",
            market="BTC/USD",
            original_nl_input="Follow trend and avoid revenge trading.",
        )
        db_session.add(playbook_a)
        db_session.add(playbook_b)
        db_session.commit()
        db_session.refresh(playbook_a)
        db_session.refresh(playbook_b)

        session_a = SessionModel(
            user_id=trader_a.id,
            playbook_id=playbook_a.id,
            start_time=now - timedelta(days=1),
            end_time=now - timedelta(days=1, hours=-1),
            status=SessionStatus.COMPLETED,
        )
        session_b = SessionModel(
            user_id=trader_b.id,
            playbook_id=playbook_b.id,
            start_time=now - timedelta(hours=2),
            status=SessionStatus.STARTED,
        )
        db_session.add(session_a)
        db_session.add(session_b)
        db_session.commit()
        db_session.refresh(session_a)
        db_session.refresh(session_b)

        events = [
            SessionEvent(
                session_id=session_a.id,
                type=SessionEventType.ADHERENCE,
                timestamp=now - timedelta(days=1, minutes=20),
                event_data={"deviation": False, "accumulated_deviation": 0},
            ),
            SessionEvent(
                session_id=session_a.id,
                type=SessionEventType.DEVIATION,
                timestamp=now - timedelta(days=1, minutes=10),
                event_data={
                    "deviation": True,
                    "accumulated_deviation": 1,
                    "deviation_family": "TIMING",
                    "deviation_type": "EARLY_ENTRY",
                    "severity": "MEDIUM",
                    "candidate_cost": 125.5,
                    "rule_name": "Wait for candle close",
                },
            ),
            SessionEvent(
                session_id=session_b.id,
                type=SessionEventType.ADHERENCE,
                timestamp=now - timedelta(hours=1, minutes=40),
                event_data={"deviation": False, "accumulated_deviation": 0},
            ),
            SessionEvent(
                session_id=session_b.id,
                type=SessionEventType.DEVIATION,
                timestamp=now - timedelta(hours=1, minutes=15),
                event_data={
                    "deviation": True,
                    "accumulated_deviation": 2,
                    "deviation_family": "RISK_PROCESS",
                    "deviation_type": "OVERSIZE",
                    "severity": "HIGH",
                    "candidate_cost": 310.0,
                    "unauthorized_gain": 40.0,
                    "rule_name": "Max Position Size",
                },
            ),
            SessionEvent(
                session_id=session_b.id,
                type=SessionEventType.DEVIATION,
                timestamp=now - timedelta(hours=1),
                event_data={
                    "deviation": True,
                    "accumulated_deviation": 3,
                    "deviation_family": "PSYCHOLOGY",
                    "deviation_type": "REVENGE_TRADE",
                    "severity": "CRITICAL",
                    "candidate_cost": 220.0,
                    "rule_name": "No Revenge Trading",
                },
            ),
        ]
        for event in events:
            db_session.add(event)
        db_session.commit()

        response = client.get("/admin/analytics/dashboard")
        assert response.status_code == 200
        payload = response.json()

        assert payload["overview"]["total_traders"] == 2
        assert payload["overview"]["active_sessions"] == 1
        assert payload["overview"]["completed_sessions"] == 1
        assert payload["overview"]["total_deviation_cost"] == 655.5
        assert payload["overview"]["total_deviation_events"] == 3
        assert payload["overview"]["at_risk_traders"] == 1

        traders = payload["traders"]
        assert traders[0]["email"] == "trader-b@example.com"
        assert traders[0]["risk_rank_label"] in {"high", "critical"}
        assert traders[0]["top_deviation_type"] == "OVERSIZE"

        interventions = payload["interventions"]
        assert interventions[0]["email"] == "trader-b@example.com"
        assert interventions[0]["priority_label"] in {"restrict", "urgent"}
        assert any("Max Position Size" in driver or "$530.00" in driver for driver in interventions[0]["drivers"])

        assert payload["deviations"]["by_family"]["RISK_PROCESS"] == 1
        assert payload["deviations"]["by_type"]["REVENGE_TRADE"] == 1
        assert payload["deviations"]["cost_by_type"]["OVERSIZE"] == 310.0

        playbooks = payload["playbooks"]
        assert playbooks[0]["playbook_name"] == "Trend Follow"
        assert playbooks[0]["total_deviation_cost"] == 530.0
    finally:
        app.dependency_overrides.pop(get_current_manager, None)
