from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session
import uuid
import logging
import httpx
from app.database import get_session
from app.schemas import PlaybookCreate
from app.routers.playbooks import create_playbook
from app.config import settings
from typing import Optional
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(tags=["utility"], prefix="/utility")
class AlpacaOrderRequest(BaseModel):
    symbol: str = "BTC/USD"
    qty: str = "0.01"
    side: str = "buy" # or "sell"
    type: str = "market"
    time_in_force: str = "gtc"



@router.post("/test-alpaca-order")
async def test_alpaca_order(order_req: AlpacaOrderRequest):
    """
    Utility endpoint to place a test order via Alpaca API using env credentials.
    """
    api_key = settings.alpaca_api_key
    api_secret = settings.alpaca_api_secret
    
    if not api_key or not api_secret:
        raise HTTPException(status_code=500, detail="Alpaca API credentials missing in environment")
        
    url = "https://paper-api.alpaca.markets/v2/orders"
    
    headers = {
        "APCA-API-KEY-ID": api_key,
        "APCA-API-SECRET-KEY": api_secret,
        "Content-Type": "application/json"
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                url, 
                headers=headers, 
                json=order_req.dict()
            )
            data = response.json()
            
            if response.status_code >= 400:
                logger.error(f"[ALPACA] Order failed: {data}")
                raise HTTPException(status_code=response.status_code, detail=f"Alpaca API error: {data}")
                
            return {
                "status": "success",
                "alpaca_response": data
            }
        except Exception as e:
            logger.error(f"[ALPACA] Request failed: {e}")
            raise HTTPException(status_code=500, detail=f"Request to Alpaca failed: {str(e)}")
