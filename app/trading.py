import logging
from app.config import settings
from app.schemas import TradeTriggerRequest, TradeTriggerResponse

logger = logging.getLogger(__name__)

# Explicitly use paper API as per user's preference
BASE_URL = "https://paper-api.alpaca.markets"

import uuid
import time
from datetime import datetime, timezone
from app.schemas import UserActivityEvent
from app.sessions import _active_sessions, get_user_for_playbook
import httpx

async def place_alpaca_order(trade_req: TradeTriggerRequest) -> TradeTriggerResponse:
    """
    Executes a trade on Alpaca using the provided request parameters.
    """
    from app.broadcast import activity_broadcaster

    url = f"{BASE_URL}/v2/orders"
    
    headers = {
        "APCA-API-KEY-ID": settings.apca_api_key,
        "APCA-API-SECRET-KEY": settings.apca_api_secret
    }
    
    payload = {
        "symbol": trade_req.symbol,
        "qty": trade_req.qty,
        "side": trade_req.side,
        "type": trade_req.type,
        "time_in_force": trade_req.time_in_force
    }
    
    try:
        logger.info(f"Sending {trade_req.side} order for {trade_req.symbol} to Alpaca...")
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload, headers=headers)
        
        if response.status_code == 200:
            order_data = response.json()
            order_id = order_data.get("id")
            logger.info(f"Order SUCCESS: {order_id}")
            
            # 🚀 IMMEDIATE BROADCAST TO ENGINE
            timestamp_iso = datetime.fromtimestamp(time.time(), tz=timezone.utc).isoformat().replace("+00:00", "Z")
            
            normalized_event = UserActivityEvent(
                activity_id=str(uuid.uuid4()),
                alpaca_event_type="new",
                order_id=order_id or "",
                symbol=trade_req.symbol,
                side=trade_req.side,
                qty=float(trade_req.qty),
                filled_qty=0.0,
                price=None,
                timestamp=timestamp_iso,
                timestamp_alpaca=time.time() * 1000,
                timestamp_server=time.time() * 1000,
                market_attachment_state="IMMEDIATE"
            )

            for playbook_id, session_id in _active_sessions.items():
                user_id = get_user_for_playbook(playbook_id)
                scoped_event = normalized_event.model_copy(
                    update={
                        "session_id": str(session_id),
                        "user_id": str(user_id) if user_id else None,
                    }
                )
                await activity_broadcaster.broadcast(
                    scoped_event.model_dump_json(exclude_none=True),
                    user_id=str(user_id) if user_id else None,
                    session_id=str(session_id)
                )
                print(f"[TRADING][BROADCAST] Immediate manual action broadcast to session {session_id}")

            return TradeTriggerResponse(status="success", order_id=order_id)
        else:
            logger.error(f"Order FAILED ({response.status_code}): {response.text}")
            return TradeTriggerResponse(status="failed", error=response.text)
            
    except Exception as e:
        logger.exception("Failed to place order due to exception")
        return TradeTriggerResponse(status="error", error=str(e))
