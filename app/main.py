import uuid
from datetime import datetime, timezone
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException
from sqlmodel import Session, select
from app.database import get_session
from app.models import Rule, UserActionRun
from app.config import settings
from app.lifecycle import on_startup, on_shutdown
from app.broadcast import MarketStateBroadcaster

from app.schemas import (
    TradeTriggerRequest, 
    TradeTriggerResponse, 
    RuleIngestRequest, 
    RuleIngestResponse,
    UserActionIngestRequest,
    UserActionIngestResponse
)
from app.trading import place_alpaca_order

app = FastAPI(title=settings.app_name)

market_broadcaster = MarketStateBroadcaster(name="MARKET_STATE")
activity_broadcaster = MarketStateBroadcaster(name="USER_ACTIVITY")

app.add_event_handler("startup", on_startup)
app.add_event_handler("shutdown", on_shutdown)

@app.get("/")
def root():
    return {
        "status": "ok",
        "service": "market_state_aggregator",
        "note": "service running, check /ws/market-state for stream"
    }

@app.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "environment": settings.environment
    }

@app.post("/trade/trigger", response_model=TradeTriggerResponse)
async def trigger_trade(trade_req: TradeTriggerRequest = TradeTriggerRequest()):
    """
    Triggers a trade on Alpaca. 
    Can be called with an empty body to use defaults (Buy 0.001 BTC/USD).
    """
    return place_alpaca_order(trade_req)


# LEGACY: Use /user-action/ingest for new rule ingestion flows.
# This endpoint is kept for backward compatibility but is deprecated.
@app.post("/rule/ingest", response_model=RuleIngestResponse)
async def ingest_rule(
    request: RuleIngestRequest, 
    db: Session = Depends(get_session)
):
    """
    Ingests a natural language rule and saves it to the database.
    """
    new_rule = Rule(rule_nl=request.rule_nl)
    db.add(new_rule)
    db.commit()
    db.refresh(new_rule)
    
    print(f"[RULE_INGEST] Saved: {new_rule.rule_nl} | ID: {new_rule.id} | TS: {new_rule.created_at}")
    
    return RuleIngestResponse(
        status="success",
        received_id=new_rule.id,
        message="Rule received and saved successfully"
    )


@app.post("/user-action/ingest", response_model=UserActionIngestResponse)
async def ingest_user_action(
    request: UserActionIngestRequest, 
    db: Session = Depends(get_session)
):
    """
    Write-only ingest:
    1. Persist raw input
    2. Set status to queued
    3. Return runId immediately
    """
    run = UserActionRun(
        user_id=request.user_id,
        action_type=request.action_type,
        raw_input_text=request.raw_input_text,
        status="queued"
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    return UserActionIngestResponse(
        runId=str(run.id),
        status=run.status
    )


# TODO: Re-introduce GET /rules when scoped by playbookId.
# This endpoint currently removed to prevent global exposure and align with playbook architecture.


@app.websocket("/ws/market-state")
async def market_state_ws(websocket: WebSocket):
    await market_broadcaster.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await market_broadcaster.disconnect(websocket)


@app.websocket("/ws/user-activity")
async def user_activity_ws(websocket: WebSocket):
    await activity_broadcaster.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await activity_broadcaster.disconnect(websocket)
