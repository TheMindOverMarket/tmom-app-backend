from fastapi import APIRouter, HTTPException, status
import httpx
import os
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from app.schemas import MarketBar, MarketHistoryResponse, MarketOption
from app.markets import FALLBACK_MARKETS, normalize_market_symbol

logger = logging.getLogger(__name__)
router = APIRouter(tags=["market-data"])

@router.get("/market-data/history", response_model=List[MarketBar])
async def get_market_history(
    symbol: str,
    timeframe: str = "1Day", 
    limit: int = 100,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None
):
    symbol = normalize_market_symbol(symbol)
    if not symbol:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A market symbol is required to load history.",
        )
    api_key = os.getenv("ALPACA_API_KEY")
    api_sec = os.getenv("ALPACA_API_SECRET")
    
    if not api_key or not api_sec:
        logger.error("[MARKET_DATA] Alpaca API credentials missing")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Market data provider credentials are not configured"
        )
    
    # Build Alpaca query parameters
    params: Dict[str, Any] = {
        "symbols": symbol,
        "timeframe": timeframe
    }
    
    if start_time:
        # If it looks like a unix timestamp (digits only), convert to ISO
        if isinstance(start_time, str) and start_time.isdigit():
            start_time = datetime.fromtimestamp(int(start_time), tz=timezone.utc).isoformat().replace("+00:00", "Z")
        params["start"] = start_time
        
    if end_time:
        # If it looks like a unix timestamp (digits only), convert to ISO
        if isinstance(end_time, str) and end_time.isdigit():
            end_time = datetime.fromtimestamp(int(end_time), tz=timezone.utc).isoformat().replace("+00:00", "Z")
        params["end"] = end_time
        
    if not start_time and not end_time:
        params["limit"] = limit
    
    url = "https://data.alpaca.markets/v1beta3/crypto/us/bars"
    headers = {
        "APCA-API-KEY-ID": api_key,
        "APCA-API-SECRET-KEY": api_sec
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers, params=params)
            
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


@router.get("/market-data/markets", response_model=List[MarketOption])
async def list_markets():
    api_key = os.getenv("ALPACA_API_KEY")
    api_sec = os.getenv("ALPACA_API_SECRET")

    if not api_key or not api_sec:
        return [MarketOption(**market) for market in FALLBACK_MARKETS]

    headers = {
        "APCA-API-KEY-ID": api_key,
        "APCA-API-SECRET-KEY": api_sec,
    }
    params = {
        "status": "active",
        "asset_class": "crypto",
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                "https://paper-api.alpaca.markets/v2/assets",
                headers=headers,
                params=params,
            )
            response.raise_for_status()
    except Exception as exc:
        logger.warning(f"[MARKET_DATA] Falling back to static market list: {exc}")
        return [MarketOption(**market) for market in FALLBACK_MARKETS]

    market_map: dict[str, MarketOption] = {}
    for asset in response.json():
        raw_symbol = str(asset.get("symbol") or "").strip()
        if not raw_symbol:
            continue

        normalized_symbol = normalize_market_symbol(raw_symbol.replace("USD", "/USD") if "/" not in raw_symbol and raw_symbol.endswith("USD") else raw_symbol)
        base_asset, quote_asset = normalized_symbol.split("/", 1)
        if quote_asset != "USD":
            continue

        display_name = asset.get("name") or f"{base_asset} / {quote_asset}"
        market_map[normalized_symbol] = MarketOption(
            symbol=normalized_symbol,
            base_asset=base_asset,
            quote_asset=quote_asset,
            display_name=display_name,
            provider="alpaca",
        )

    if not market_map:
        return [MarketOption(**market) for market in FALLBACK_MARKETS]

    return sorted(market_map.values(), key=lambda market: market.symbol)
