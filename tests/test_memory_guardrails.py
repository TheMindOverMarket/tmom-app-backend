import asyncio
import uuid
from datetime import datetime, timezone

from aggregator.indicators.symbol_state import SymbolState
from app import sessions
from app.models import SessionEventType


def test_symbol_snapshot_copies_indicator_maps_without_deepcopying_scalars():
    state = SymbolState("BTC/USD")
    state.last_price = 123.45
    state.indicator_cache["1m"] = {"EMA_20": 100.0}

    snapshot = state.get_snapshot()

    snapshot["indicator_values"]["1m"]["EMA_20"] = 999.0

    assert state.indicator_cache["1m"]["EMA_20"] == 100.0


def test_log_session_event_drops_when_queue_is_full():
    playbook_id = uuid.uuid4()
    session_id = uuid.uuid4()
    user_id = uuid.uuid4()

    sessions.clear_active_sessions()
    sessions.set_active_session(playbook_id, session_id, user_id, "BTC/USD")

    drained = []
    try:
        while True:
            drained.append(sessions._event_queue.get_nowait())
    except asyncio.QueueEmpty:
        pass

    try:
        sessions._dropped_event_count = 0
        while not sessions._event_queue.full():
            sessions._event_queue.put_nowait(
                {
                    "session_id": session_id,
                    "type": SessionEventType.SYSTEM,
                    "tick": None,
                    "event_data": {"seed": True},
                    "event_metadata": None,
                    "timestamp": datetime.now(timezone.utc),
                }
            )

        sessions.log_session_event(
            playbook_id=playbook_id,
            event_type=SessionEventType.SYSTEM,
            event_data={"action": "OVERFLOW"},
        )

        assert sessions._event_queue.qsize() == sessions._event_queue.maxsize
        assert sessions._dropped_event_count == 1
    finally:
        try:
            while True:
                sessions._event_queue.get_nowait()
                sessions._event_queue.task_done()
        except asyncio.QueueEmpty:
            pass

        for item in drained:
            sessions._event_queue.put_nowait(item)

        sessions.clear_active_sessions()
