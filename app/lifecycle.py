import asyncio
import logging
from typing import Any, Optional
from dotenv import load_dotenv
from app.alpaca_ws import AlpacaCryptoStream, AlpacaTradingStream
from app.session_runtime import sync_runtime_from_database
from aggregator.indicators.indicator_registry import IndicatorRegistry
from aggregator.engine.candle_engine import CandleEngine

load_dotenv()

logger = logging.getLogger(__name__)

_stream_task: Optional[asyncio.Task] = None
_trading_stream_task: Optional[asyncio.Task] = None
_session_worker_task: Optional[asyncio.Task] = None
_stream: Optional[AlpacaCryptoStream] = None
_trading_stream: Optional[AlpacaTradingStream] = None

# New Architecture Components
indicator_registry: IndicatorRegistry = IndicatorRegistry()
candle_engine: CandleEngine = CandleEngine(indicator_registry)


async def on_startup() -> None:
    global _stream_task, _stream, _trading_stream_task, _trading_stream

    _stream = AlpacaCryptoStream()
    _trading_stream = AlpacaTradingStream()

    runtime_summary = await sync_runtime_from_database()
    logger.info(f"[LIFECYCLE][STARTUP] Runtime restored: {runtime_summary}")

    async def run_stream():
        print("Starting AlpacaCryptoStream task")
        await _stream.start()

    async def run_trading_stream():
        print("Starting AlpacaTradingStream task")
        await _trading_stream.start()

    _stream_task = asyncio.create_task(run_stream())
    _trading_stream_task = asyncio.create_task(run_trading_stream())
    
    # Start high-performance session logger background worker
    from app.sessions import process_event_batch_worker
    _session_worker_task = asyncio.create_task(process_event_batch_worker())


async def on_shutdown() -> None:
    # Trigger graceful shutdown sequence
    print("[LIFECYCLE][SHUTDOWN] Starting shutdown sequence...")
    
    global _stream_task, _stream, _trading_stream_task, _trading_stream

    # Stop streams first to close internal sockets and exit loops naturally
    if _stream:
        print("[LIFECYCLE][SHUTDOWN] Stopping AlpacaCryptoStream...")
        await _stream.stop()

    if _trading_stream:
        print("[LIFECYCLE][SHUTDOWN] Stopping AlpacaTradingStream...")
        await _trading_stream.stop()

    # Cancel tasks to unblock awaitable calls if they are stuck
    if _stream_task:
        print("[LIFECYCLE][SHUTDOWN] Cancelling Market Data Task...")
        _stream_task.cancel()
        try:
            # We await the cancelled task to ensure legacy cleanup finishes
            await _stream_task
        except asyncio.CancelledError:
            # Expected during shutdown
            print("[LIFECYCLE][SHUTDOWN] Market Data Task cancelled successfully")

    if _trading_stream_task:
        print("[LIFECYCLE][SHUTDOWN] Cancelling Trading Data Task...")
        _trading_stream_task.cancel()
        try:
            await _trading_stream_task
        except asyncio.CancelledError:
             print("[LIFECYCLE][SHUTDOWN] Trading Data Task cancelled successfully")

    # Finalize and flush background session logging
    from app.sessions import shutdown_event_worker
    await shutdown_event_worker()
    if _session_worker_task:
        _session_worker_task.cancel()
        try:
            await _session_worker_task
        except asyncio.CancelledError:
            print("[LIFECYCLE][SHUTDOWN] Session Logger Task finalized")
             
    print("[LIFECYCLE][SHUTDOWN] Shutdown sequence complete")


def get_runtime_status() -> dict[str, Any]:
    from app.sessions import _active_sessions

    return {
        "active_session_count": len(_active_sessions),
        "market_stream": _stream.status_snapshot() if _stream else {"running": False, "connected": False},
        "trading_stream": _trading_stream.status_snapshot() if _trading_stream else {"running": False, "connected": False},
    }
