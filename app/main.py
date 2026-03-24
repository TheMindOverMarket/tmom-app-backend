from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Depends, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import logging
from app.config import settings
from contextlib import asynccontextmanager
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

@asynccontextmanager
async def lifespan(app: FastAPI):
    await on_startup()
    yield
    await on_shutdown()

app = FastAPI(title=settings.app_name, lifespan=lifespan)

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

@app.post("/trade", response_model=TradeTriggerResponse)
def execute_trade(trade_req: TradeTriggerRequest):
    """
    Executes a buy or sell on Alpaca. The trade update 
    will flow through the user-activity stream via background websockets.
    """
    return place_alpaca_order(trade_req)

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
    await market_broadcaster.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await market_broadcaster.disconnect(websocket)

@app.websocket("/ws/market-data")
async def market_data_ws(websocket: WebSocket):
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
