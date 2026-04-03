from __future__ import annotations

from typing import Any


FALLBACK_MARKETS: list[dict[str, str]] = [
    {"symbol": "BTC/USD", "base_asset": "BTC", "quote_asset": "USD", "display_name": "Bitcoin / US Dollar", "provider": "fallback"},
    {"symbol": "ETH/USD", "base_asset": "ETH", "quote_asset": "USD", "display_name": "Ethereum / US Dollar", "provider": "fallback"},
    {"symbol": "SOL/USD", "base_asset": "SOL", "quote_asset": "USD", "display_name": "Solana / US Dollar", "provider": "fallback"},
    {"symbol": "DOGE/USD", "base_asset": "DOGE", "quote_asset": "USD", "display_name": "Dogecoin / US Dollar", "provider": "fallback"},
    {"symbol": "LTC/USD", "base_asset": "LTC", "quote_asset": "USD", "display_name": "Litecoin / US Dollar", "provider": "fallback"},
    {"symbol": "AVAX/USD", "base_asset": "AVAX", "quote_asset": "USD", "display_name": "Avalanche / US Dollar", "provider": "fallback"},
]


def normalize_market_symbol(value: str | None) -> str:
    if not value:
        return "BTC/USD"

    normalized = value.strip().upper().replace("-", "/")
    if not normalized:
        return "BTC/USD"

    if "/" not in normalized:
        normalized = f"{normalized}/USD"

    base_asset, quote_asset = normalized.split("/", 1)
    base_asset = base_asset.strip()
    quote_asset = quote_asset.strip() or "USD"
    if not base_asset:
        base_asset = "BTC"

    return f"{base_asset}/{quote_asset}"


def build_market_context(context: dict[str, Any] | None, market: str) -> dict[str, Any]:
    synced_context = dict(context or {})
    synced_context["symbol"] = market
    return synced_context


def resolve_playbook_market(playbook: Any) -> str:
    explicit_market = getattr(playbook, "market", None)
    if explicit_market:
        return normalize_market_symbol(explicit_market)

    context = getattr(playbook, "context", None) or {}
    return normalize_market_symbol(context.get("symbol"))
