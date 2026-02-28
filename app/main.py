from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.lifecycle import on_startup, on_shutdown
from app.broadcast import MarketStateBroadcaster
from app.routers import (
    users, 
    playbooks, 
    rules, 
    conditions, 
    condition_edges,
    market_data
)

app = FastAPI(title=settings.app_name)

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
    print(f"Unhandled exception: {exc}")
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error: {str(exc)}"}
    )

# Broadcasters for streaming
market_broadcaster = MarketStateBroadcaster(name="MARKET_STATE")
activity_broadcaster = MarketStateBroadcaster(name="USER_ACTIVITY")

app.add_event_handler("startup", on_startup)
app.add_event_handler("shutdown", on_shutdown)

# Include Domain Routers
app.include_router(users.router)
app.include_router(playbooks.router)
app.include_router(rules.router)
app.include_router(conditions.router)
app.include_router(condition_edges.router)
app.include_router(market_data.router)

@app.get("/")
def root():
    return {
        "status": "ok",
        "service": "tmom-domain-api",
        "note": "Domain CRUD operational"
    }

@app.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "environment": settings.environment
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
