import requests
import logging
from app.config import settings
from app.schemas import TradeTriggerRequest, TradeTriggerResponse

logger = logging.getLogger(__name__)

# Explicitly use paper API as per user's preference
BASE_URL = "https://paper-api.alpaca.markets"

def place_alpaca_order(trade_req: TradeTriggerRequest) -> TradeTriggerResponse:
    """
    Executes a trade on Alpaca using the provided request parameters.
    """
    url = f"{BASE_URL}/v2/orders"
    
    headers = {
        "APCA-API-KEY-ID": settings.alpaca_api_key,
        "APCA-API-SECRET-KEY": settings.alpaca_api_secret
    }
    
    payload = {
        "symbol": trade_req.symbol,
        "qty": trade_req.qty,
        "side": trade_req.side,
        "type": trade_req.type,
        "time_in_force": trade_req.time_in_force
    }
    
    try:
        logger.info(f"Sending {trade_req.side} order for {trade_req.qty} {trade_req.symbol} to Alpaca...")
        response = requests.post(url, json=payload, headers=headers)
        
        if response.status_code == 200:
            order_data = response.json()
            order_id = order_data.get("id")
            logger.info(f"Order SUCCESS: {order_id}")
            return TradeTriggerResponse(status="success", order_id=order_id)
        else:
            logger.error(f"Order FAILED ({response.status_code}): {response.text}")
            return TradeTriggerResponse(status="failed", error=response.text)
            
    except Exception as e:
        logger.exception("Failed to place order due to exception")
        return TradeTriggerResponse(status="error", error=str(e))
