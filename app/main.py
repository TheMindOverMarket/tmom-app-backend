from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Depends, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import logging
from app.config import settings
from app.database import get_session
from app.lifecycle import on_startup, on_shutdown
from app.broadcast import MarketStateBroadcaster
from app.routers import (
    users, 
    playbooks, 
    rules, 
    conditions, 
    condition_edges,
    market_data,
    utility,
    sessions
)
from app.schemas import TradeTriggerRequest, TradeTriggerResponse
from app.trading import place_alpaca_order



# Configure professional logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

from contextlib import asynccontextmanager
@asynccontextmanager
async def app_lifespan(app: FastAPI):
    await on_startup()
    yield
    await on_shutdown()

app = FastAPI(title=settings.app_name, lifespan=app_lifespan)



# Strict Canonical CORS Middleware Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://tmom-app-frontend.vercel.app",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS", "PUT", "DELETE", "PATCH"],
    allow_headers=["*"],
)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    import traceback
    # Log the full stack trace internally
    logger.error(f"Unhandled exception: {exc}")
    logger.error(traceback.format_exc())
    
    # Return a clean error message to the client
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "An internal server error occurred. Our team has been notified.",
            "type": exc.__class__.__name__
        }
    )

# Broadcasters for streaming
market_broadcaster = MarketStateBroadcaster(name="MARKET_STATE")
activity_broadcaster = MarketStateBroadcaster(name="USER_ACTIVITY")

# Include Domain Routers
app.include_router(users.router)
app.include_router(playbooks.router)
app.include_router(rules.router)
app.include_router(conditions.router)
app.include_router(condition_edges.router)
app.include_router(market_data.router)
app.include_router(utility.router)
app.include_router(sessions.router)

@app.get("/")
def root():
    return {
        "status": "ok",
        "service": "tmom-domain-api",
        "note": "Domain CRUD operational"
    }

@app.post("/trade", response_model=TradeTriggerResponse, tags=["Trading"])
def execute_trade(trade_req: TradeTriggerRequest):
    """
    Executes a buy or sell on Alpaca. The trade update 
    will flow through the user-activity stream via background websockets.
    """
    return place_alpaca_order(trade_req)

@app.post("/mock-trade", response_model=TradeTriggerResponse, tags=["Trading"])
async def execute_mock_trade(trade_req: TradeTriggerRequest):
    """
    Executes a mock trade and directly pushes it to the user-activity stream.
    Used for frontend testing without relying on Alpaca WebSocket.
    """
    import uuid
    import time
    from app.schemas import UserActivityEvent
    from app.sessions import log_session_event, _active_sessions
    from app.models import SessionEventType

    order_id = str(uuid.uuid4())
    
    normalized_event = UserActivityEvent(
        activity_id=str(uuid.uuid4()),
        alpaca_event_type="fill",
        order_id=order_id,
        symbol=trade_req.symbol,
        side=trade_req.side,
        qty=float(trade_req.qty),
        filled_qty=float(trade_req.qty),
        price=100000.0,
        timestamp_alpaca=time.time() * 1000,
        timestamp_server=time.time() * 1000,
        market_attachment_state="MOCK",
        market_snapshot_id=None,
        market_ref_age_ms=None
    )
    
    await activity_broadcaster.broadcast(normalized_event.model_dump_json())
    logger.info(f"[MOCK_TRADE] Emitted mock user activity for {trade_req.symbol}")
    
    for playbook_id in _active_sessions.keys():
        log_session_event(
            playbook_id=playbook_id,
            event_type=SessionEventType.TRADING,
            event_data=normalized_event.model_dump(),
            event_metadata={"alpaca_event": "mock_fill"}
        )
        
    return TradeTriggerResponse(status="success", order_id=order_id)

@app.get("/health")
async def health(db = Depends(get_session)) -> dict:
    from sqlmodel import text
    try:
        # Simple query to test DB connectivity
        db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        logger.error(f"Health check DB failure: {e}")
        db_status = "unavailable"

    return {
        "status": "ok" if db_status == "connected" else "degraded",
        "environment": settings.environment,
        "database": db_status
    }


@app.websocket("/ws/market-state")
async def market_state_ws(websocket: WebSocket):
    user_id = websocket.query_params.get("user_id")
    session_id = websocket.query_params.get("session_id")
    await market_broadcaster.connect(websocket, user_id=user_id, session_id=session_id)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await market_broadcaster.disconnect(websocket, user_id=user_id, session_id=session_id)

@app.websocket("/ws/engine-output")
async def engine_output_ws(websocket: WebSocket):
    """Alias for market-state, strictly for frontend alignment."""
    user_id = websocket.query_params.get("user_id")
    session_id = websocket.query_params.get("session_id")
    await market_broadcaster.connect(websocket, user_id=user_id, session_id=session_id)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await market_broadcaster.disconnect(websocket, user_id=user_id, session_id=session_id)

@app.websocket("/ws/market-data")
async def market_data_ws(websocket: WebSocket):
    user_id = websocket.query_params.get("user_id")
    session_id = websocket.query_params.get("session_id")
    await market_broadcaster.connect(websocket, user_id=user_id, session_id=session_id)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await market_broadcaster.disconnect(websocket, user_id=user_id, session_id=session_id)

@app.websocket("/ws/user-activity")
async def user_activity_ws(websocket: WebSocket):
    user_id = websocket.query_params.get("user_id")
    session_id = websocket.query_params.get("session_id")
    await activity_broadcaster.connect(websocket, user_id=user_id, session_id=session_id)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await activity_broadcaster.disconnect(websocket, user_id=user_id, session_id=session_id)
