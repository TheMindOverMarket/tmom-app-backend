import asyncio


async def on_startup() -> None:
    """
    Application startup hook.
    Background tasks (e.g., websocket consumers) will be attached here later.
    """
    pass


async def on_shutdown() -> None:
    """
    Application shutdown hook.
    Used to gracefully close websocket connections and tasks.
    """
    pass
