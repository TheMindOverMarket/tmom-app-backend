from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session
import uuid
import logging
import httpx
from app.database import get_session
from app.schemas.playbooks import PlaybookCreate
from app.routers.playbooks import create_playbook
from app.config import settings
from typing import Optional
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(tags=["utility"], prefix="/utility")

HARDCODED_PROMPT = """
I’m using BTC. 
1. Setup Logic (Deterministic Inputs)

Derived State:
	•	Session VWAP (UTC daily reset)
	•	20-period EMA
	•	14-period ATR
	•	Rolling volatility regime
	•	Daily realized PnL

⸻

Long Setup

Conditions must ALL be true:
	1.	Price < VWAP − 1.5 × ATR
	2.	EMA slope > 0
	3.	5-min close back above prior candle high
	4.	Not within 10 minutes of previous stop

⸻

Short Setup
	1.	Price > VWAP + 1.5 × ATR
	2.	EMA slope < 0
	3.	5-min close below prior candle low
	4.	Not within 10 minutes of previous stop

⸻

2. Entry Rules
	•	Market order at next candle open.
	•	Max 1 position at a time.
	•	No pyramiding.
	•	No flipping within 5 minutes.

⸻

3. Risk Model

Stop: 1 ATR
Target: 2 ATR
Trailing stop activates at +1R
Max daily loss: 3R
Max 5 trades per UTC day
Position size: 1% account risk per trade

⸻

4. Meta Discipline Rules (Where TMOM Shines)

Hard Constraints:
	•	Block trade if daily loss ≥ 3R
	•	Block if > 5 trades
	•	Block if position size > 1% risk

Soft Guardrails:
	•	Warn if trade taken within 3 minutes of prior close
	•	Warn if volatility > 95th percentile
	•	Require justification if third consecutive loss

Cooldown:
	•	10 minutes after stop loss
	•	30 minutes after 2 consecutive losses
"""

class AlpacaOrderRequest(BaseModel):
    symbol: str = "BTC/USD"
    qty: str = "0.001"
    side: str = "buy" # or "sell"
    type: str = "market"
    time_in_force: str = "gtc"


@router.post("/create-sample-playbook")
async def create_sample_playbook(db: Session = Depends(get_session)):
    """
    Utility endpoint to create a playbook with a hardcoded prompt and user.
    """
    user_id = uuid.UUID("1d4d88c7-bcd1-4813-8f34-59c9776e5b3f")
    
    playbook_data = PlaybookCreate(
        name="Sample BTC Ruleset",
        user_id=user_id,
        original_nl_input=HARDCODED_PROMPT,
        context={
            "description": "Auto-generated sample playbook from utility endpoint",
            "symbol": "BTC/USD"
        }
    )
    
    return await create_playbook(playbook_in=playbook_data, db=db)


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
