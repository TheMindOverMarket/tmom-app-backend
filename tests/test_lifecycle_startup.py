import pytest
from unittest.mock import AsyncMock, patch

from app import lifecycle


@pytest.mark.asyncio
async def test_startup_continues_when_alpaca_credentials_are_missing() -> None:
    with patch("app.alpaca_ws.os.getenv", return_value=""), patch(
        "app.lifecycle.sync_runtime_from_database", new_callable=AsyncMock, return_value={}
    ), patch(
        "app.sessions.process_event_batch_worker", new_callable=AsyncMock
    ):
        await lifecycle.on_startup()

    runtime = lifecycle.get_runtime_status()
    assert runtime["market_stream"]["running"] is False
    assert runtime["trading_stream"]["running"] is False
    assert any("alpaca_streams_unavailable" in issue for issue in runtime["startup_issues"])
