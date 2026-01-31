from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from app.config import settings
from app.lifecycle import on_startup, on_shutdown
from app.broadcast import MarketStateBroadcaster

app = FastAPI(title=settings.app_name)

market_broadcaster = MarketStateBroadcaster()
activity_broadcaster = MarketStateBroadcaster()

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
