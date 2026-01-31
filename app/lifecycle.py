import asyncio
from typing import Optional
from dotenv import load_dotenv
from app.alpaca_ws import AlpacaCryptoStream, AlpacaTradingStream

load_dotenv()

_stream_task: Optional[asyncio.Task] = None
_trading_stream_task: Optional[asyncio.Task] = None
_stream: Optional[AlpacaCryptoStream] = None
_trading_stream: Optional[AlpacaTradingStream] = None


async def on_startup() -> None:
    global _stream_task, _stream

    _stream = AlpacaCryptoStream()
    _trading_stream = AlpacaTradingStream()

    async def run_stream():
        print("Starting AlpacaCryptoStream task")
        await _stream.start()

    async def run_trading_stream():
        print("Starting AlpacaTradingStream task")
        await _trading_stream.start()

    _stream_task = asyncio.create_task(run_stream())
    _trading_stream_task = asyncio.create_task(run_trading_stream())


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
             
    print("[LIFECYCLE][SHUTDOWN] Shutdown sequence complete")
