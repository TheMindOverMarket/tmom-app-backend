from fastapi import APIRouter
import urllib.request
import json
import os
from datetime import datetime

router = APIRouter(tags=["market-data"])

@router.get("/market-data/history")
async def get_market_history(symbol: str = "BTC/USD", timeframe: str = "1Day", limit: int = 100):
    api_key = os.getenv("ALPACA_API_KEY")
    api_sec = os.getenv("ALPACA_API_SECRET")
    
    # Alpaca Explicit API Request
    url = f"https://data.alpaca.markets/v1beta3/crypto/us/bars?symbols={symbol}&timeframe={timeframe}&limit={limit}"
    req = urllib.request.Request(url, headers={"APCA-API-KEY-ID": api_key, "APCA-API-SECRET-KEY": api_sec})
    
    try:
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            bars = data.get("bars", {}).get(symbol, [])
            
            # Format required by lightweight-charts: time (Unix Epoch Seconds), open, high, low, close
            formatted_bars = []
            for bar in bars:
                dt_str = bar["t"]
                if dt_str.endswith("Z"):
                    dt_str = dt_str[:-1] + "+00:00"
                dt = datetime.fromisoformat(dt_str)
                
                formatted_bars.append({
                    "time": int(dt.timestamp()), # strictly unix epoch seconds
                    "open": bar["o"],
                    "high": bar["h"],
                    "low": bar["l"],
                    "close": bar["c"]
                })
            
            return formatted_bars
    except Exception as e:
        return {"error": str(e)}
