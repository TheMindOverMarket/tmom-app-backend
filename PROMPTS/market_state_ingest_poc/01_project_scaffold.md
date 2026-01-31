# 01_project_scaffold.md

> **Purpose**  
> Create a clean FastAPI + asyncio WebSocket-ready service skeleton.  
> No Alpaca logic. No business logic. No premature abstractions.

---

## Objective

Set up a minimal FastAPI application that:

- Can run locally
- Is ready to host async background tasks
- Is ready to host WebSocket endpoints
- Establishes a clean project structure for streaming services

This file **must not** include:
- Alpaca connections
- Market data logic
- Event schemas beyond placeholders

---

## Project Structure to Create

```
app/
  main.py
  config.py
  lifecycle.py
  __init__.py

requirements.txt
README.md
```

---

## Implementation Instructions

### 1. `requirements.txt`

Create a `requirements.txt` with **only** the following dependencies:

```
fastapi
uvicorn[standard]
pydantic
python-dotenv
websockets
```

Do **not** add Alpaca SDKs yet.

---

### 2. `app/config.py`

Create a config module that:

- Loads environment variables
- Exposes a typed settings object
- Does not hardcode secrets

```python
from pydantic import BaseSettings


class Settings(BaseSettings):
    app_name: str = "market-data-aggregator"
    environment: str = "local"

    class Config:
        env_file = ".env"


settings = Settings()
```

---

### 3. `app/lifecycle.py`

Create lifecycle hooks for future background tasks.

```python
import asyncio


async def on_startup() -> None:
    """
    Application startup hook.
    Background tasks (e.g., websocket consumers) will be attached here later.
    """
    pass


async def on_shutdown() -> None:
    """
    Application shutdown hook.
    Used to gracefully close websocket connections and tasks.
    """
    pass
```

No logic yet. Just structure.

---

### 4. `app/main.py`

Create the FastAPI application with:

- Startup and shutdown hooks
- A health check endpoint
- No WebSocket endpoints yet

```python
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
```

---

### 5. `README.md`

Create a minimal README explaining how to run the service.

```md
# Market Data Aggregator

Minimal FastAPI service that ingests live market data and streams normalized events downstream.

## Running locally

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Health check

Visit:

http://localhost:8000/health
```

---

## Acceptance Criteria (must verify)

After executing this file:

- `uvicorn app.main:app --reload` starts successfully
- `/health` returns `200 OK`
- No unused imports
- No warnings about event loops
- No Alpaca references anywhere

---

## Notes for Future Files

- Background asyncio tasks will be registered in `on_startup`
- Alpaca WebSocket client will live in its own module
- Outbound event streaming will be layered later

---

## End of File 01
