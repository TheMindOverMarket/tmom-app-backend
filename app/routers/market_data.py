from fastapi import APIRouter, HTTPException, status
import httpx
import os
import logging
from datetime import datetime
from typing import List, Dict, Any
from app.schemas import MarketBar, MarketHistoryResponse

logger = logging.getLogger(__name__)
router = APIRouter(tags=["market-data"])

@router.get("/market-data/history", response_model=List[MarketBar])
async def get_market_history(symbol: str = "BTC/USD", timeframe: str = "1Day", limit: int = 100):
    api_key = os.getenv("ALPACA_API_KEY")
    api_sec = os.getenv("ALPACA_API_SECRET")
    
    if not api_key or not api_sec:
        logger.error("[MARKET_DATA] Alpaca API credentials missing")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Market data provider credentials are not configured"
        )
    
    # Alpaca Explicit API Request
    url = f"https://data.alpaca.markets/v1beta3/crypto/us/bars?symbols={symbol}&timeframe={timeframe}&limit={limit}"
    headers = {
        "APCA-API-KEY-ID": api_key,
        "APCA-API-SECRET-KEY": api_sec
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers)
            
            if response.status_code == 401:
                logger.error(f"[MARKET_DATA] Unauthorized call to Alpaca: {response.text}")
                raise HTTPException(status_code=401, detail="Invalid API credentials for market data provider")
            
            if response.status_code != 200:
                logger.error(f"[MARKET_DATA] Alpaca API returned {response.status_code}: {response.text}")
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Error from market data provider: {response.text}"
                )
                
            data = response.json()
            bars = data.get("bars", {}).get(symbol, [])
            
            if not bars:
                logger.warning(f"[MARKET_DATA] No bar data found for symbol: {symbol}")
                return []

            # Format required by lightweight-charts: time (Unix Epoch Seconds), open, high, low, close
            formatted_bars = []
            for bar in bars:
                try:
                    dt_str = bar["t"]
                    if dt_str.endswith("Z"):
                        dt_str = dt_str[:-1] + "+00:00"
                    dt = datetime.fromisoformat(dt_str)
                    
                    formatted_bars.append(MarketBar(
                        time=int(dt.timestamp()), # strictly unix epoch seconds
                        open=float(bar["o"]),
                        high=float(bar["h"]),
                        low=float(bar["l"]),
                        close=float(bar["c"])
                    ))
                except (KeyError, ValueError) as e:
                    logger.error(f"[MARKET_DATA] Error parsing bar data: {str(e)}")
                    continue # Skip malformed bars
                
            return formatted_bars
            
        except httpx.RequestError as e:
            logger.error(f"[MARKET_DATA] Request failed: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Market data provider is currently unreachable"
            )
        except Exception as e:
            logger.exception("[MARKET_DATA] Unexpected error occurred")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An unexpected error occurred while fetching market data"
            )

