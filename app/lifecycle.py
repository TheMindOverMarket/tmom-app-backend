import asyncio
import logging
from typing import Any, Optional
from dotenv import load_dotenv
from app.config import settings

load_dotenv()

logger = logging.getLogger(__name__)

_stream_task: Optional[asyncio.Task] = None
_trading_stream_task: Optional[asyncio.Task] = None
_session_worker_task: Optional[asyncio.Task] = None
_stream: Optional[Any] = None
_trading_stream: Optional[Any] = None
_startup_issues: list[str] = []

# New Architecture Components
indicator_registry: Optional[Any] = None
candle_engine: Optional[Any] = None


def ensure_runtime_components() -> tuple[Any, Any]:
    """
    Lazily construct the indicator runtime so cold starts do not eagerly import
    NumPy / TA-Lib unless a session runtime actually needs them.
    """
    global indicator_registry, candle_engine

    if indicator_registry is None or candle_engine is None:
        from aggregator.indicators.indicator_registry import IndicatorRegistry
        from aggregator.engine.candle_engine import CandleEngine

        indicator_registry = IndicatorRegistry()
        candle_engine = CandleEngine(indicator_registry)
        logger.info("[LIFECYCLE][RUNTIME] Indicator runtime initialized lazily.")

    return indicator_registry, candle_engine


async def sync_runtime_from_database() -> dict[str, Any]:
    from app.session_runtime import sync_runtime_from_database as _sync_runtime_from_database

    return await _sync_runtime_from_database()


async def on_startup() -> None:
    global _stream_task, _stream, _trading_stream_task, _trading_stream, _startup_issues, _session_worker_task

    _startup_issues = []
    _stream = None
    _trading_stream = None

    if settings.enable_live_market_streams:
        try:
            from app.alpaca_ws import AlpacaCryptoStream, AlpacaTradingStream

            _stream = AlpacaCryptoStream()
            _trading_stream = AlpacaTradingStream()
        except Exception as exc:
            issue = f"alpaca_streams_unavailable: {exc}"
            _startup_issues.append(issue)
            logger.warning(
                "[LIFECYCLE][STARTUP] Alpaca stream bootstrap skipped; API will start without live streams: %s",
                exc,
            )
    else:
        issue = "alpaca_streams_disabled_by_config"
        _startup_issues.append(issue)
        logger.info("[LIFECYCLE][STARTUP] Live Alpaca streams disabled by configuration.")

    if settings.enable_runtime_recovery:
        try:
            ensure_runtime_components()
            runtime_summary = await sync_runtime_from_database()
            logger.info(f"[LIFECYCLE][STARTUP] Runtime restored: {runtime_summary}")
        except Exception as exc:
            issue = f"runtime_sync_failed: {exc}"
            _startup_issues.append(issue)
            logger.exception("[LIFECYCLE][STARTUP] Runtime sync failed; continuing with empty in-memory state.")
    else:
        issue = "runtime_recovery_disabled_by_config"
        _startup_issues.append(issue)
        logger.info("[LIFECYCLE][STARTUP] Runtime recovery disabled by configuration.")

    async def run_stream():
        print("Starting AlpacaCryptoStream task")
        await _stream.start()

    async def run_trading_stream():
        print("Starting AlpacaTradingStream task")
        await _trading_stream.start()

    _stream_task = None
    _trading_stream_task = None
    if _stream is not None:
        _stream_task = asyncio.create_task(run_stream())
    if _trading_stream is not None:
        _trading_stream_task = asyncio.create_task(run_trading_stream())
    
    # Start high-performance session logger background worker
    from app.sessions import process_event_batch_worker, start_event_worker

    start_event_worker()
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
        "startup_issues": list(_startup_issues),
    }
