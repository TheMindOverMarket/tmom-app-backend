# TheMindOverMarket - Backend Service

This FastAPI service acts as the central data storage and routing hub for TMOM. It manages Playbooks, User Sessions, Deviation Analytics, and proxying historical market data.

## Architecture

The backend primarily provides REST APIs for the frontend to interact with the Supabase PostgreSQL database. It is NOT responsible for real-time live trading loops—that task is delegated to the `Rule-Engine` service.

**Core Endpoints:**
- `/playbooks`: CRUD and compiling LLM playbooks (via Rule-Engine proxy).
- `/sessions`: Managing active and completed trading sessions.
- `/deviations`: Serving deviation records, analytics, and session summaries.
- `/market-data`: Proxying historical bar data from Alpaca/Binance to the frontend.

## Running locally

```bash
cp .env.example .env
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

Required backend env:
- `DATABASE_URL` (Supabase Postgres)
- `ALPACA_API_KEY`
- `ALPACA_API_SECRET`
- `RULE_ENGINE_URL` (URL of the local/remote Rule Engine)

## Health check

Visit:
http://localhost:8000/health
