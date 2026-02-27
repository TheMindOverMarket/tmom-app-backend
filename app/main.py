import uuid
from datetime import datetime, timezone
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends
from sqlmodel import Session, select
from app.database import get_session
from app.config import settings
from app.lifecycle import on_startup, on_shutdown
from app.broadcast import MarketStateBroadcaster

from app.schemas import (
    TradeTriggerRequest, 
    TradeTriggerResponse, 
    RuleIngestRequest, 
    RuleIngestResponse
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
