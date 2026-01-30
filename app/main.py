from fastapi import FastAPI
from app.config import settings
from app.lifecycle import on_startup, on_shutdown

app = FastAPI(title=settings.app_name)

app.add_event_handler("startup", on_startup)
app.add_event_handler("shutdown", on_shutdown)


@app.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "environment": settings.environment
    }
