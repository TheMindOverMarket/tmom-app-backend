from datetime import datetime, timezone

from aggregator.engine.candle_engine import CandleEngine
from aggregator.indicators.indicator_registry import IndicatorRegistry
from aggregator.models import NormalizedBar, NormalizedTick


def test_hydration_vwap_uses_latest_utc_day_and_real_volume():
    engine = CandleEngine(IndicatorRegistry())

    bars = [
        NormalizedBar(
            symbol="BTC/USD",
            timeframe="1m",
            open=100.0,
            high=100.0,
            low=100.0,
            close=100.0,
            volume=10.0,
            start_time=datetime(2026, 4, 8, 23, 59, tzinfo=timezone.utc),
        ),
        NormalizedBar(
            symbol="BTC/USD",
            timeframe="1m",
            open=200.0,
            high=200.0,
            low=200.0,
            close=200.0,
            volume=2.0,
            start_time=datetime(2026, 4, 9, 0, 0, tzinfo=timezone.utc),
        ),
        NormalizedBar(
            symbol="BTC/USD",
            timeframe="1m",
            open=300.0,
            high=300.0,
            low=300.0,
            close=300.0,
            volume=4.0,
            start_time=datetime(2026, 4, 9, 0, 1, tzinfo=timezone.utc),
        ),
    ]

    engine.hydrate_historical_bars("BTC/USD", bars)
    snapshot = engine.get_symbol_state("BTC/USD").get_snapshot()

    expected_vwap = ((200.0 * 2.0) + (300.0 * 4.0)) / (2.0 + 4.0)
    assert snapshot["vwap"] == expected_vwap


def test_live_vwap_resets_on_utc_day_boundary():
    engine = CandleEngine(IndicatorRegistry())

    engine.ingest_tick(
        NormalizedTick(
            symbol="BTC/USD",
            timestamp=datetime(2026, 4, 8, 23, 59, 50, tzinfo=timezone.utc),
            price=100.0,
            size=2.0,
        )
    )
    before_reset = engine.get_symbol_state("BTC/USD").get_snapshot()
    assert before_reset["vwap"] == 100.0

    engine.ingest_tick(
        NormalizedTick(
            symbol="BTC/USD",
            timestamp=datetime(2026, 4, 9, 0, 0, 5, tzinfo=timezone.utc),
            price=400.0,
            size=1.0,
        )
    )
    after_reset = engine.get_symbol_state("BTC/USD").get_snapshot()

    assert after_reset["vwap"] == 400.0
