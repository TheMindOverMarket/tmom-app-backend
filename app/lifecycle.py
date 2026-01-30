import asyncio
from typing import Optional
from dotenv import load_dotenv
from app.alpaca_ws import AlpacaCryptoStream

load_dotenv()

_stream_task: Optional[asyncio.Task] = None
_stream: Optional[AlpacaCryptoStream] = None


async def on_startup() -> None:
    global _stream_task, _stream

    _stream = AlpacaCryptoStream()

    async def run_stream():
        print("Starting AlpacaCryptoStream task")
        await _stream.start()

    _stream_task = asyncio.create_task(run_stream())


async def on_shutdown() -> None:
    global _stream_task, _stream

    if _stream:
        await _stream.stop()

    if _stream_task:
        _stream_task.cancel()
        try:
            await _stream_task
        except asyncio.CancelledError:
            pass
