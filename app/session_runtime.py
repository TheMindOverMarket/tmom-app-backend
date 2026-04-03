from __future__ import annotations
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict

from sqlmodel import Session, select

from aggregator.models import NormalizedBar
from app.database import engine
from app.models import Playbook, Session as SessionModel, SessionStatus
from app.routers.market_data import get_market_history
from app.sessions import clear_active_sessions, set_active_session
from app.markets import normalize_market_symbol, resolve_playbook_symbol

logger = logging.getLogger(__name__)


def normalize_indicator_request(metric: object) -> tuple[str | None, str, dict]:
    """
    Accept either the rule-engine's TA-Lib metric objects or plain string market-data
    fields and normalize them into the registry's expected shape.
    """
    if isinstance(metric, dict):
        name = metric.get("name")
        timeframe = metric.get("timeframe", "1m")
        params = metric.get("params", {})
        return name, timeframe, params if isinstance(params, dict) else {}

    if isinstance(metric, str):
        return metric, "1m", {}

    return None, "1m", {}


def get_alpaca_symbol(context: Dict[str, Any] | None) -> str:
    return normalize_market_symbol((context or {}).get("symbol"))


def iter_indicator_requests(context: Dict[str, Any] | None):
    context = context or {}
    ta_lib_metrics = context.get("ta_lib_metrics", [])
    market_data_config = context.get("market_data", [])
    all_metrics = list(ta_lib_metrics) + list(market_data_config)

    for metric in all_metrics:
        name, timeframe, params = normalize_indicator_request(metric)
        if not name:
            logger.warning(f"[SESSION][RUNTIME] Skipping malformed metric config: {metric!r}")
            continue
        yield name, timeframe, params


async def sync_runtime_from_database() -> dict[str, Any]:
    """
    Rebuild in-memory runtime state from persisted STARTED sessions so the backend can
    recover after a deploy, cold start, or process restart.
    """
    import app.lifecycle

    active_symbols: set[str] = set()
    hydrated_symbols: set[str] = set()
    registered_metric_keys: set[tuple[str, str, str]] = set()
    restored_sessions = 0

    clear_active_sessions()

    if app.lifecycle.indicator_registry:
        app.lifecycle.indicator_registry.clear()

    if app.lifecycle.candle_engine:
        app.lifecycle.candle_engine.clear_all()

    if app.lifecycle._stream:
        app.lifecycle._stream.latest_market_state.clear()

    with Session(engine) as db:
        started_sessions = db.exec(
            select(SessionModel)
            .where(SessionModel.status == SessionStatus.STARTED)
            .order_by(SessionModel.created_at.asc())
        ).all()

        for db_session in started_sessions:
            playbook = db.get(Playbook, db_session.playbook_id)
            if not playbook:
                logger.warning(
                    f"[SESSION][RUNTIME] Skipping restore for session {db_session.id}: "
                    f"playbook {db_session.playbook_id} not found."
                )
                continue

            restored_sessions += 1
            context = playbook.context or {"symbol": resolve_playbook_symbol(playbook)}
            alpaca_symbol = get_alpaca_symbol(context)
            set_active_session(playbook.id, db_session.id, db_session.user_id, alpaca_symbol)
            active_symbols.add(alpaca_symbol)

            if app.lifecycle.indicator_registry:
                for name, timeframe, params in iter_indicator_requests(context):
                    metric_key = (
                        name,
                        timeframe,
                        json.dumps(params, sort_keys=True, separators=(",", ":")),
                    )
                    if metric_key in registered_metric_keys:
                        continue
                    registered_metric_keys.add(metric_key)
                    app.lifecycle.indicator_registry.register(
                        name=name,
                        timeframe=timeframe,
                        params=params,
                    )

    if app.lifecycle._stream:
        await app.lifecycle._stream.sync_symbols(active_symbols)

    for symbol in sorted(active_symbols):
        if symbol in hydrated_symbols:
            continue
        try:
            market_bars = await get_market_history(symbol=symbol, timeframe="1Min", limit=300)
            if market_bars and app.lifecycle.candle_engine:
                normalized_bars = [
                    NormalizedBar(
                        symbol=symbol,
                        timeframe="1m",
                        open=float(bar.open),
                        high=float(bar.high),
                        low=float(bar.low),
                        close=float(bar.close),
                        volume=0.0,
                        start_time=datetime.fromtimestamp(bar.time, tz=timezone.utc),
                    )
                    for bar in market_bars
                ]
                app.lifecycle.candle_engine.hydrate_historical_bars(symbol, normalized_bars)
                if app.lifecycle._stream:
                    snapshot = app.lifecycle.candle_engine.get_symbol_state(symbol).get_snapshot()
                    app.lifecycle._stream.latest_market_state[symbol] = snapshot
                hydrated_symbols.add(symbol)
                logger.info(
                    f"[SESSION][RUNTIME] Hydrated runtime state for {symbol} with "
                    f"{len(normalized_bars)} bars during sync."
                )
            else:
                logger.warning(f"[SESSION][RUNTIME] No market bars available while syncing {symbol}.")
        except Exception as exc:
            logger.warning(f"[SESSION][RUNTIME] Failed to hydrate {symbol} during sync: {exc}")

    summary = {
        "restored_sessions": restored_sessions,
        "tracked_symbols": sorted(active_symbols),
        "registered_metrics": len(registered_metric_keys),
    }
    logger.info(f"[SESSION][RUNTIME] Sync complete: {summary}")
    return summary
