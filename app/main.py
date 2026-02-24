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
    UserActionIngestResponse,
    UserActionRunResponse
)
from app.trading import place_alpaca_order
from app.rule_engine.parser import parse_user_rule

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
    Synchronous end-to-end ingestion flow:
    1. Persist raw input
    2. Run logic (structured output)
    3. Update record
    4. Return result
    """
    # 1. Create UserActionRun row
    run = UserActionRun(
        user_id=request.user_id,
        action_type=request.action_type,
        raw_input_text=request.raw_input_text,
        status="pending"
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    # 2. Call rule parsing / rule engine logic
    rule_output = parse_user_rule(request.raw_input_text)

    # 3. Update the same row
    run.rule_output_json = rule_output
    run.status = "processed"
    run.updated_at = datetime.now(timezone.utc)

    db.add(run)
    db.commit()
    db.refresh(run)

    # 4. Return promptId + structured rule JSON
    return UserActionIngestResponse(
        promptId=str(run.id),
        status=run.status,
        rule_output_json=run.rule_output_json
    )


@app.get("/user-action/{prompt_id}", response_model=UserActionRunResponse)
async def get_user_action(
    prompt_id: uuid.UUID,
    db: Session = Depends(get_session)
):
    """
    Fetches a single UserActionRun by its ID. Returns 404 if not found.
    """
    run = db.exec(select(UserActionRun).where(UserActionRun.id == prompt_id)).first()
    
    if not run:
        raise HTTPException(status_code=404, detail="UserActionRun not found")
        
    return UserActionRunResponse(
        promptId=str(run.id),
        userId=run.user_id,
        actionType=run.action_type,
        rawInputText=run.raw_input_text,
        ruleOutputJson=run.rule_output_json,
        status=run.status,
        createdAt=run.created_at.isoformat(),
        updatedAt=run.updated_at.isoformat()
    )


@app.get("/rules")
async def get_rules(db: Session = Depends(get_session)):
    """
    Returns all ingested rules.
    """
    from sqlmodel import select
    rules = db.exec(select(Rule)).all()
    return rules


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
