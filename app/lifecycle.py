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
    global _stream_task, _stream, _trading_stream_task, _trading_stream

    if _stream:
        await _stream.stop()

    if _trading_stream:
        await _trading_stream.stop()

    if _stream_task:
        _stream_task.cancel()
        try:
            await _stream_task
        except asyncio.CancelledError:
            pass

    if _trading_stream_task:
        _trading_stream_task.cancel()
        try:
            await _trading_stream_task
        except asyncio.CancelledError:
            pass
