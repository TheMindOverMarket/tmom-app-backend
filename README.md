# Market Data Aggregator

Minimal FastAPI service that ingests live market data and streams normalized events downstream.

## Running locally

```bash
cp .env.example .env
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

Required backend env:

- `DATABASE_URL`
- `ALPACA_API_KEY`
- `ALPACA_API_SECRET`

The backend uses Alpaca paper endpoints for both order submission and `trade_updates`.

## Paper Trade Smoke Test

With the backend running and env vars loaded, submit a paper order directly:

```bash
curl -X POST http://localhost:8000/utility/test-alpaca-order \
  -H 'Content-Type: application/json' \
  -d '{"symbol":"BTC/USD","qty":"0.001","side":"buy","type":"market","time_in_force":"gtc"}'
```

For TMOM to ingest and broadcast the resulting trade update into the app, you also need at least one active TMOM session.

## Health check

Visit:

http://localhost:8000/health
