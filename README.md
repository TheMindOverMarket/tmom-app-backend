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
