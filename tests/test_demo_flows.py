import pytest
import uuid
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi import status
from sqlmodel import Session, select
from app.models import Playbook, Rule, Condition, GenerationStatus, SessionStatus, User
from app.schemas import MarketBar

@pytest.mark.asyncio
async def test_demo_flow_lifecycle(client, db_session: Session, test_user: User):
    """
    Complete Demo Trail Implementation:
    1. Create/Ingest Playbook (Extraction Success)
    2. Start Session (Integrity Verification)
    3. Historical Market Data Integrity
    4. Trading Execution (Mock Alpaca)
    """

    # --- FLOW 1: Playbook Ingestion & Extraction ---
    # We mock the intelligence module so it doesn't try to call an LLM
    with patch("app.routers.playbooks.analyze_playbook_execution") as mock_extract:
        playbook_payload = {
            "name": "Demo Strategy",
            "user_id": str(test_user.id),
            "original_nl_input": "I want to buy BTC when price is below VWAP."
        }
        
        response = client.post("/playbooks/ingest", json=playbook_payload)
        assert response.status_code == status.HTTP_201_CREATED
        playbook_data = response.json()
        playbook_id = uuid.UUID(playbook_data["id"])
        assert playbook_data["generation_status"] == "PENDING"
        
        # Verify background task was triggered
        mock_extract.assert_called_once()

    # MANUALLY SIMULATE EXTRACTION COMPLETION (The "Rules Show" portion of demo)
    # In a real demo, the background agent does this. In tests, we verify the backend's
    # ability to handle the COMPLETED state and rules.
    pb = db_session.get(Playbook, playbook_id)
    pb.generation_status = GenerationStatus.COMPLETED
    pb.context = {"symbol": "BTC/USD"}
    db_session.add(pb)
    
    # Add rules and conditions so the session start integrity check passes
    rule = Rule(playbook_id=playbook_id, name="VWAP Cross", category="logic")
    db_session.add(rule)
    db_session.flush()
    
    condition = Condition(rule_id=rule.id, metric="price", comparator="<", value="vwap")
    db_session.add(condition)
    db_session.commit()

    # --- FLOW 2: Session Lifecycle (Start) ---
    with patch("app.routers.sessions.trigger_session_execution") as mock_exec, \
         patch("app.routers.sessions.sync_runtime_from_database", new_callable=AsyncMock):
        
        session_payload = {
            "user_id": str(test_user.id),
            "playbook_id": str(playbook_id),
            "session_metadata": {"demo": True}
        }
        
        response = client.post("/sessions/start", json=session_payload)
        assert response.status_code == status.HTTP_200_OK
        session_data = response.json()
        assert session_data["status"] == "STARTED"
        assert session_data["playbook_id"] == str(playbook_id)
        
        # Verify engine was triggered
        mock_exec.assert_called_once()

    # --- FLOW 3: Market Data Integrity ---
    # Test the historical fetch used by ReplayPlayer
    with patch("httpx.AsyncClient.get") as mock_get:
        # Mock Alpaca response for crypto bars
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "bars": {
                "BTC/USD": [
                    {"t": "2024-03-27T10:00:00Z", "o": 65000, "h": 66000, "l": 64000, "c": 65500, "v": 10},
                    {"t": "2024-03-27T10:01:00Z", "o": 65500, "h": 67000, "l": 65000, "c": 66500, "v": 15}
                ]
            }
        }
        mock_get.return_value = mock_response
        
        # Test with start_time/end_time (new params)
        params = {
            "symbol": "BTC/USD",
            "timeframe": "1Min",
            "start_time": "1711533600", # Example timestamp
            "end_time": "1711533660"
        }
        response = client.get("/market-data/history", params=params)
        assert response.status_code == 200
        bars = response.json()
        assert len(bars) == 2
        assert bars[0]["close"] == 65500
        assert "time" in bars[0] # Verify unix epoch format

    # --- FLOW 4: Trade Trigger (Mock Alpaca) ---
    # Demo Flow: "do a buy/sell and see the change reflected"
    with patch("app.trading.requests.post") as mock_alpaca_post:
        # Mock successful order execution
        mock_alpaca_response = MagicMock()
        mock_alpaca_response.status_code = 200
        mock_alpaca_response.json.return_value = {"id": "test-order-uuid-123"}
        mock_alpaca_post.return_value = mock_alpaca_response
        
        trade_payload = {
            "symbol": "BTC/USD",
            "qty": "0.1",
            "side": "buy",
            "type": "market",
            "time_in_force": "gtc"
        }
        
        response = client.post("/trade", json=trade_payload)
        assert response.status_code == 200
        trade_result = response.json()
        assert trade_result["status"] == "success"
        assert trade_result["order_id"] == "test-order-uuid-123"
        
        # Verify call to Alpaca was made with correct params
        called_args, called_kwargs = mock_alpaca_post.call_args
        assert called_kwargs["json"]["symbol"] == "BTC/USD"
        assert called_kwargs["json"]["side"] == "buy"

@pytest.mark.asyncio
async def test_health_check(client):
    """Verify system health check and DB connectivity."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["database"] == "connected"
