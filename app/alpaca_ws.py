import asyncio
import json
import logging
import os
import websockets
import uuid
import time
from datetime import datetime, timezone
from aggregator.models import NormalizedTick
import app.lifecycle
from app.sessions import log_session_event
from app.models import SessionEventType
from app.schemas import UserActivityEvent

logger = logging.getLogger(__name__)

ALPACA_CRYPTO_WS_URL = "wss://stream.data.alpaca.markets/v1beta3/crypto/us"
ALPACA_TRADING_WS_URL = "wss://paper-api.alpaca.markets/stream"


class AlpacaBaseStream:
    def __init__(self, url: str) -> None:
        self._api_key = os.getenv("ALPACA_API_KEY")
        self._api_secret = os.getenv("ALPACA_API_SECRET")
        self.ws_url = url
        self._ws = None
        self._running = True

        if not self._api_key or not self._api_secret:
            raise RuntimeError("Missing Alpaca API credentials")

    async def connect(self):
        print(f"[{self.__class__.__name__}][CONNECTING] Initiating connection to {self.ws_url}")
        return websockets.connect(
            self.ws_url,
            ping_interval=20,
            ping_timeout=20,
            open_timeout=10,
            close_timeout=5,
            max_queue=None,
        )

    async def authenticate(self) -> None:
        auth_message = {
            "action": "auth",
            "key": self._api_key,
            "secret": self._api_secret
        }
        await self._ws.send(json.dumps(auth_message))
        print(f"[{self.__class__.__name__}][AUTH_SENT] Auth message sent")

    async def stop(self) -> None:
        # Signal the loop to stop processing messages
        print(f"[{self.__class__.__name__}][STOPPING] Setting running flag to False")
        self._running = False
        if self._ws:
            try:
                # Explicitly close socket to unblock any pending recv() calls
                print(f"[{self.__class__.__name__}][CLOSING_SOCKET] Closing WebSocket connection")
                await self._ws.close()
            except Exception as e:
                print(f"[{self.__class__.__name__}][STOP_ERROR] Error closing websocket: {e}")


class AlpacaCryptoStream(AlpacaBaseStream):
    def __init__(self) -> None:
        super().__init__(ALPACA_CRYPTO_WS_URL)
        self.symbols = ["BTC/USD"]
        self.latest_market_state = {}  # Stores {symbol: event_dict}

    async def start(self) -> None:
        # Import inside the function to avoid circular dependency
        from app.main import market_broadcaster

    async def start(self) -> None:
        # Import inside the function to avoid circular dependency
        from app.main import market_broadcaster

        print("[STREAM][STARTED] AlpacaCryptoStream task running")
        print(f"[ALPACA][CONNECT] Connecting to {self.ws_url}")

        async with await self.connect() as ws:
            print("[ALPACA][CONNECTED] WebSocket connection established")
            self._ws = ws
            await self.authenticate()
            await self._subscribe()

            # Add a background task for periodic broadcasting (1s)
            broadcast_task = asyncio.create_task(self._broadcast_loop())

            while self._running:
                try:
                    if not self._running:
                        break
                        
                    message = await ws.recv()
                    # print(f"[ALPACA][RECEIVED_RAW] {message}") # Verbose
                    
                    try:
                        data = json.loads(message)
                        if isinstance(data, list):
                            for obj in data:
                                msg_type = obj.get("T")
                                if msg_type in ["q", "t"]:
                                    symbol = obj.get("S")
                                    ts_str = obj.get("t")
                                    
                                    # Parse timestamp (Strictly from data stream)
                                    if not ts_str:
                                        continue
                                    ts = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))

                                    price = 0.0
                                    size = 0.0
                                    
                                    if msg_type == "q":
                                        bp = obj.get("bp")
                                        ap = obj.get("ap")
                                        if bp is not None and ap is not None:
                                            price = (bp + ap) / 2
                                        size = (obj.get("bs", 0) + obj.get("as", 0)) / 2
                                    else: # Trade
                                        price = obj.get("p", 0.0)
                                        size = obj.get("s", 0.0)

                                    if price > 0:
                                        # 1️⃣ Normalize Ingestion Layer
                                        tick = NormalizedTick(
                                            symbol=symbol,
                                            timestamp=ts,
                                            price=price,
                                            size=size
                                        )

                                        # 2️⃣ Canonical Candle Engine (Injest Tick)
                                        import app.lifecycle
                                        if app.lifecycle.candle_engine:
                                            app.lifecycle.candle_engine.ingest_tick(tick)
                                            
                                            # Update local cache for immediate snapshot access
                                            state = app.lifecycle.candle_engine.get_symbol_state(symbol)
                                            # 5️⃣ MarketState Snapshot (No longer inject legacy raw_timestamp_ms)
                                            snapshot = state.get_snapshot()
                                            self.latest_market_state[symbol] = snapshot

                                            # Tick-by-tick logic (Behavioral) can go here
                                            # But indicators are NOT recalculated here.

                                else:
                                    logger.debug(f"[ALPACA][IGNORED] Message type {msg_type} not relevant")
                    except Exception as e:
                        logger.error(f"Error processing message logic: {e}")
                        
                except asyncio.CancelledError:
                    break
                except websockets.ConnectionClosed:
                    break
                except Exception as e:
                    logger.error(f"[ALPACA][ERROR] Loop error: {e}")
            
            broadcast_task.cancel()
        
        print(f"[{self.__class__.__name__}][EXITED_CLEANLY] Background task finished")

    async def _broadcast_loop(self) -> None:
        """
        6️⃣ Broadcast Behavior (UNCHANGED FREQUENCY)
        Decoupled broadcast loop running at ~1Hz.
        """
        from app.main import market_broadcaster
        
        while self._running:
            try:
                await asyncio.sleep(1.0)
                
                for symbol, snapshot in self.latest_market_state.items():
                    # Legacy timestamp for frontend compatibility
                    # 6️⃣ Broadcast Behavior - Deterministic Timestamp
                    raw_ts = snapshot["last_tick_timestamp_ms"]
                    current_time_str = datetime.fromtimestamp(raw_ts / 1000, timezone.utc).isoformat().replace("+00:00", "Z")
                    
                    from app.schemas import MarketStateEvent
                    event = MarketStateEvent(
                        symbol=symbol,
                        timestamp=current_time_str,
                        current_time=current_time_str,
                        price=snapshot["last_price"],
                        high=snapshot["current_candle_high"],
                        low=snapshot["current_candle_low"],
                        indicator_values=snapshot["indicator_values"] # Metrics derived automatically
                    )
                    
                    # 🚀 SCOPED BROADCAST TO ALL ACTIVE SESSIONS
                    from app.sessions import _active_sessions
                    
                    if _active_sessions:
                        for playbook_id, session_id in _active_sessions.items():
                            # Broadcast specifically to this session's subscribers
                            await market_broadcaster.broadcast(
                                event.model_dump_json(), 
                                session_id=str(session_id)
                            )
                    else:
                        # Fallback: Global broadcast if no specific sessions are active 
                        # (useful for generic monitoring)
                        await market_broadcaster.broadcast(event.model_dump_json())
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[BROADCAST_LOOP][ERROR] {e}")
        
        print(f"[{self.__class__.__name__}][EXITED_CLEANLY] Background task finished")

    async def _subscribe(self) -> None:
        subscribe_message = {
            "action": "subscribe",
            "quotes": self.symbols
        }
        await self._ws.send(json.dumps(subscribe_message))
        print(f"[ALPACA][SUBSCRIBE_SENT] Subscribed to quotes: {self.symbols}")


class AlpacaTradingStream(AlpacaBaseStream):
    def __init__(self) -> None:
        super().__init__(ALPACA_TRADING_WS_URL)

    async def start(self) -> None:
        print("[STREAM][STARTED] AlpacaTradingStream task running")
        print(f"[ALPACA_TRADING][CONNECT] Connecting to {self.ws_url}")

        try:
            async with await self.connect() as ws:
                print("[ALPACA_TRADING][CONNECTED] WebSocket connection established")
                self._ws = ws
                await self.authenticate()
                await self._subscribe()

                while self._running:
                    try:
                        if not self._running:
                            break
                            
                        message = await ws.recv()
                        print(f"[ALPACA][TRADE_UPDATE][RECEIVED] {message}")

                        try:
                            data = json.loads(message)
                            stream = data.get("stream")
                            if stream == "trade_updates":
                                payload = data.get("data", {})
                                event_type = payload.get("event")
                                execution = payload.get("order", {})

                                # Extract fields
                                order_id = execution.get("id")
                                symbol = execution.get("symbol")
                                side = execution.get("side")
                                qty = float(execution.get("qty") or 0)
                                filled_qty = float(execution.get("filled_qty") or 0)

                                # Price logic
                                raw_price = execution.get("filled_avg_price")
                                price = float(raw_price) if raw_price else None

                                # Timestamp logic
                                raw_ts = payload.get("timestamp")
                                ts_alpaca = 0.0
                                if raw_ts:
                                    if isinstance(raw_ts, str):
                                        try:
                                            dt = datetime.fromisoformat(raw_ts.replace('Z', '+00:00'))
                                            ts_alpaca = dt.timestamp() * 1000  # to ms
                                        except ValueError:
                                            pass
                                    elif isinstance(raw_ts, (int, float)):
                                        if raw_ts > 1000000000000000:
                                            ts_alpaca = raw_ts / 1000000
                                        else:
                                            ts_alpaca = raw_ts

                                # Create Normalized Event with ISO Timestamp
                                timestamp_iso = datetime.fromtimestamp(time.time(), tz=timezone.utc).isoformat().replace("+00:00", "Z")
                                
                                normalized_event = UserActivityEvent(
                                    activity_id=str(uuid.uuid4()),
                                    alpaca_event_type=event_type or "unknown",
                                    order_id=order_id or "",
                                    symbol=symbol or "",
                                    side=side or "",
                                    qty=qty,
                                    filled_qty=filled_qty,
                                    price=price,
                                    timestamp=timestamp_iso,
                                    timestamp_alpaca=ts_alpaca,
                                    timestamp_server=time.time() * 1000
                                )

                                print(f"[USER_ACTIVITY][NORMALIZED] {normalized_event.model_dump_json()}")

                                # Context Attachment (MD 4 Requirement)
                                from app.lifecycle import _stream as crypto_stream_instance

                                attachment_state = "UNATTACHED"
                                market_ref_age_ms = None
                                market_snapshot_id = None

                                # Configuration for freshness
                                MARKET_STATE_FRESHNESS_MS = 5000

                                if crypto_stream_instance:
                                    # Normalize symbol lookup.
                                    latest_state = crypto_stream_instance.latest_market_state.get(symbol)

                                    if latest_state:
                                        market_ts = latest_state["last_tick_timestamp_ms"]
                                        activity_ts = normalized_event.timestamp_server

                                        if market_ts and market_ts <= activity_ts:
                                            age = activity_ts - market_ts
                                            market_ref_age_ms = age
                                            market_snapshot_id = f"{symbol}_{market_ts}"

                                            if age <= MARKET_STATE_FRESHNESS_MS:
                                                attachment_state = "ATTACHED"
                                            else:
                                                attachment_state = "ATTACHED_STALE"
                                        else:
                                            attachment_state = "UNATTACHED"

                                # Enrich event
                                normalized_event.market_attachment_state = attachment_state
                                normalized_event.market_snapshot_id = market_snapshot_id
                                normalized_event.market_ref_age_ms = market_ref_age_ms

                                print(f"[USER_ACTIVITY][ENRICHED] {normalized_event.model_dump_json()}")

                                # 🚀 ANALYTICS LOGGING & SCOPED BROADCAST
                                from app.sessions import _active_sessions, get_user_for_playbook
                                from app.main import activity_broadcaster
                                
                                for playbook_id, session_id in _active_sessions.items():
                                    user_id = get_user_for_playbook(playbook_id)
                                    
                                    # 1. Scoped Broadcast to the specific session/user WebSocket
                                    await activity_broadcaster.broadcast(
                                        normalized_event.model_dump_json(), 
                                        user_id=str(user_id) if user_id else None,
                                        session_id=str(session_id)
                                    )
                                    print(f"[USER_ACTIVITY][EMITTED] Scoped to Session: {session_id}")

                                    # 2. Database Analytics Logging
                                    log_session_event(
                                        playbook_id=playbook_id,
                                        event_type=SessionEventType.TRADING,
                                        event_data=normalized_event.model_dump(),
                                        event_metadata={"alpaca_event": event_type}
                                    )

                        except json.JSONDecodeError:
                            pass
                        except Exception as e:
                            print(f"[ALPACA_TRADING][ERROR] Normalization failed: {e}")

                    except asyncio.CancelledError:
                        # Expected when task is cancelled during app shutdown
                        print("[ALPACA_TRADING][CANCELLED] Task cancelled, exiting loop")
                        break
                    except websockets.ConnectionClosed:
                        # Expected when socket is closed explicitly
                        if self._running:
                            print("[ALPACA_TRADING][CLOSED] Connection closed unexpectedly")
                        else:
                            print("[ALPACA_TRADING][CLOSED] Connection closed cleanly (Intentional)")
                        break
                    except Exception as e:
                        print(f"[ALPACA_TRADING][ERROR] Loop error: {e}")

        except Exception as e:
            print(f"[ALPACA_TRADING][ERROR] Connection failed: {e}")
        
        print(f"[{self.__class__.__name__}][EXITED_CLEANLY] Background task finished")

    async def _subscribe(self) -> None:
        subscribe_message = {
            "action": "listen",
            "data": {
                "streams": ["trade_updates"]
            }
        }
        await self._ws.send(json.dumps(subscribe_message))
        print(f"[ALPACA_TRADING][SUBSCRIBE_SENT] Subscribed to trade_updates")
