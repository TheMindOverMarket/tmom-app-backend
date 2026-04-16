import uuid
import asyncio
import logging
from typing import Dict, Optional, List, Any
from datetime import datetime, timezone
from sqlmodel import Session, select
from app.database import engine
from app.models import SessionEvent, SessionEventType
from app.config import settings

logger = logging.getLogger(__name__)

# Global registry of active sessions
# Key: playbook_id (UUID), Value: session_id (UUID)
_active_sessions: Dict[uuid.UUID, uuid.UUID] = {}
# Key: playbook_id (UUID), Value: user_id (UUID)
_playbook_to_user: Dict[uuid.UUID, uuid.UUID] = {}
# Key: symbol (str), Value: Set of user_id (UUID)
_symbol_to_users: Dict[str, set[uuid.UUID]] = {}
# Key: playbook_id (UUID), Value: symbol (str)
_playbook_to_symbol: Dict[uuid.UUID, str] = {}

# High-Performance Logging Queue
_event_queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue(maxsize=settings.session_event_queue_maxsize)
_running = True
_dropped_event_count = 0


def start_event_worker() -> None:
    global _running
    _running = True


def _queue_depth() -> int:
    return _event_queue.qsize()


def _drain_batch(max_items: int) -> list[Dict[str, Any]]:
    batch: list[Dict[str, Any]] = []
    while len(batch) < max_items:
        try:
            batch.append(_event_queue.get_nowait())
        except asyncio.QueueEmpty:
            break
    return batch

def set_active_session(playbook_id: uuid.UUID, session_id: uuid.UUID, user_id: uuid.UUID, symbol: str):
    _active_sessions[playbook_id] = session_id
    _playbook_to_user[playbook_id] = user_id
    _playbook_to_symbol[playbook_id] = symbol
    
    if symbol not in _symbol_to_users:
        _symbol_to_users[symbol] = set()
    _symbol_to_users[symbol].add(user_id)

def get_active_session(playbook_id: uuid.UUID) -> Optional[uuid.UUID]:
    return _active_sessions.get(playbook_id)

def get_user_for_playbook(playbook_id: uuid.UUID) -> Optional[uuid.UUID]:
    return _playbook_to_user.get(playbook_id)

def remove_active_session(playbook_id: uuid.UUID):
    user_id = _playbook_to_user.get(playbook_id)
    symbol = _playbook_to_symbol.get(playbook_id)
    
    if playbook_id in _active_sessions:
        del _active_sessions[playbook_id]
    if playbook_id in _playbook_to_user:
        del _playbook_to_user[playbook_id]
    if playbook_id in _playbook_to_symbol:
        del _playbook_to_symbol[playbook_id]
        
    if symbol and user_id and symbol in _symbol_to_users:
        _symbol_to_users[symbol].discard(user_id)
        if not _symbol_to_users[symbol]:
            del _symbol_to_users[symbol]


def clear_active_sessions():
    _active_sessions.clear()
    _playbook_to_user.clear()
    _playbook_to_symbol.clear()
    _symbol_to_users.clear()


def get_users_for_symbol(symbol: str) -> set[uuid.UUID]:
    """Returns the set of users interested in a given symbol."""
    return _symbol_to_users.get(symbol, set())

def log_session_event(
    playbook_id: uuid.UUID,
    event_type: SessionEventType,
    event_data: dict,
    tick: Optional[int] = None,
    event_metadata: Optional[dict] = None
):
    """
    NON-BLOCKING: Enqueues a session event for background batch processing.
    Ensures that the API remains responsive during high-volatility events.
    """
    session_id = get_active_session(playbook_id)
    if not session_id:
        return

    global _dropped_event_count

    queued_event = {
        "session_id": session_id,
        "type": event_type,
        "tick": tick,
        "event_data": event_data,
        "event_metadata": event_metadata,
        "timestamp": datetime.now(timezone.utc)
    }

    try:
        _event_queue.put_nowait(queued_event)
    except asyncio.QueueFull:
        _dropped_event_count += 1
        if _dropped_event_count in {1, 10, 100} or _dropped_event_count % 1000 == 0:
            logger.warning(
                "[SESSIONS][WORKER] Event queue full at %s items; dropped %s session events.",
                _queue_depth(),
                _dropped_event_count,
            )

async def process_event_batch_worker():
    """
    Continuous background task that polls the queue and flushes batches to the DB.
    """
    global _running
    logger.info("[SESSIONS][WORKER] Background event logger started.")
    
    while _running:
        try:
            # 1. Wait for at least one event
            event = await _event_queue.get()
            batch = [event]

            # 2. Try to grab more events immediately available (up to 50)
            batch.extend(_drain_batch(max_items=49))
            
            # 3. Flushes the batch in a single transaction
            if batch:
                with Session(engine) as db:
                    for e in batch:
                        new_event = SessionEvent(
                            session_id=e["session_id"],
                            type=e["type"],
                            tick=e["tick"],
                            event_data=e["event_data"],
                            event_metadata=e["event_metadata"],
                            timestamp=e["timestamp"]
                        )
                        db.add(new_event)
                    db.commit()
                
                # Signal completion for each task if anyone is awaiting the queue join (e.g., shutdown)
                for _ in batch:
                    _event_queue.task_done()
                    
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"[SESSIONS][WORKER][ERROR] Batch flush failed: {e}", exc_info=True)
            # Short sleep to prevent tight loop during persistent DB issues
            await asyncio.sleep(1.0)

async def shutdown_event_worker():
    """
    Gracefully flush remaining items before stopping.
    """
    global _running
    _running = False
    
    logger.info("[SESSIONS][WORKER] Shutting down. Flushing final items...")
    # Give it one final chance to clear everything
    if not _event_queue.empty():
        while not _event_queue.empty():
            try:
                batch = _drain_batch(max_items=50)
                if not batch:
                    break
                with Session(engine) as db:
                    for event in batch:
                        new_event = SessionEvent(
                            session_id=event["session_id"],
                            type=event["type"],
                            tick=event["tick"],
                            event_data=event["event_data"],
                            event_metadata=event["event_metadata"],
                            timestamp=event["timestamp"]
                        )
                        db.add(new_event)
                    db.commit()
                for _ in batch:
                    _event_queue.task_done()
            except Exception:
                break
    logger.info("[SESSIONS][WORKER] Shutdown complete.")
