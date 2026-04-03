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
        return ""

    normalized = value.strip().upper().replace("-", "/")
    if not normalized:
        return ""

    if "/" not in normalized:
        normalized = f"{normalized}/USD"

    base_asset, quote_asset = normalized.split("/", 1)
    base_asset = base_asset.strip()
    quote_asset = quote_asset.strip() or "USD"
    if not base_asset:
        return ""

    return f"{base_asset}/{quote_asset}"


def build_market_context(context: dict[str, Any] | None, symbol: str | None) -> dict[str, Any]:
    synced_context = dict(context or {})
    normalized_symbol = normalize_market_symbol(symbol or synced_context.get("symbol"))
    if normalized_symbol:
        synced_context["symbol"] = normalized_symbol
    return synced_context


def sync_playbook_market_state(
    *,
    symbol: str | None = None,
    market: str | None = None,
    context: dict[str, Any] | None = None,
) -> tuple[str | None, str | None, dict[str, Any]]:
    canonical_symbol = normalize_market_symbol(symbol or market or (context or {}).get("symbol"))
    return canonical_symbol or None, canonical_symbol or None, build_market_context(context, canonical_symbol)


def resolve_playbook_symbol(playbook: Any) -> str:
    explicit_symbol = getattr(playbook, "symbol", None)
    if explicit_symbol:
        return normalize_market_symbol(explicit_symbol)

    explicit_market = getattr(playbook, "market", None)
    if explicit_market:
        return normalize_market_symbol(explicit_market)

    context = getattr(playbook, "context", None) or {}
    return normalize_market_symbol(context.get("symbol"))


def resolve_playbook_market(playbook: Any) -> str:
    return resolve_playbook_symbol(playbook)
