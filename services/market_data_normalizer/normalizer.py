"""Market data normalization layer.

Standardizes incoming price feeds from multiple exchanges (Binance, Coinbase,
Alpaca) into a unified internal format.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Unified internal schema fields.
REQUIRED_FIELDS = ("symbol", "exchange", "timestamp")
NUMERIC_FIELDS = ("bid", "ask", "last_price", "volume_24h", "vwap")

# Default symbol map: maps exchange-specific symbols to internal format.
DEFAULT_SYMBOL_MAP: Dict[str, str] = {
    "BTCUSD": "BTC/USD",
    "BTC-USD": "BTC/USD",
    "ETHUSD": "ETH/USD",
    "ETH-USD": "ETH/USD",
    "SOLUSD": "SOL/USD",
    "SOL-USD": "SOL/USD",
    "DOGEUSD": "DOGE/USD",
    "DOGE-USD": "DOGE/USD",
}


class NormalizedTick:
    """Unified market data tick."""

    __slots__ = (
        "symbol",
        "exchange",
        "timestamp",
        "bid",
        "ask",
        "last_price",
        "volume_24h",
        "vwap",
    )

    def __init__(
        self,
        symbol: str,
        exchange: str,
        timestamp: str,
        bid: Optional[float] = None,
        ask: Optional[float] = None,
        last_price: Optional[float] = None,
        volume_24h: Optional[float] = None,
        vwap: Optional[float] = None,
    ):
        self.symbol = symbol
        self.exchange = exchange
        self.timestamp = timestamp
        self.bid = bid
        self.ask = ask
        self.last_price = last_price
        self.volume_24h = volume_24h
        self.vwap = vwap

    def to_dict(self) -> Dict[str, Any]:
        return {s: getattr(self, s) for s in self.__slots__}


class ValidationError(Exception):
    """Raised when normalized data fails validation."""


def _resolve_symbol(raw_symbol: str, symbol_map: Dict[str, str]) -> str:
    """Resolve an exchange-specific symbol to the internal format."""
    if raw_symbol in symbol_map:
        return symbol_map[raw_symbol]
    # Already in internal format (contains '/').
    if "/" in raw_symbol:
        return raw_symbol
    logger.warning("Unknown symbol format: %s — passing through as-is", raw_symbol)
    return raw_symbol


def _safe_float(value: Any, field_name: str, exchange: str) -> Optional[float]:
    """Convert a value to float, returning None and logging on failure."""
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        logger.warning(
            "Cannot convert %s=%r to float for exchange %s", field_name, value, exchange
        )
        return None


def _parse_timestamp(value: Any) -> Optional[str]:
    """Parse various timestamp formats to ISO-8601 UTC string."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        # Epoch seconds or milliseconds.
        ts = value if value < 1e12 else value / 1000.0
        return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
    if isinstance(value, str):
        return value
    return str(value)


def validate(tick: NormalizedTick) -> List[str]:
    """Validate a normalized tick. Returns list of error messages (empty = valid)."""
    errors: List[str] = []
    if not tick.symbol:
        errors.append("symbol is empty")
    if not tick.exchange:
        errors.append("exchange is empty")
    if not tick.timestamp:
        errors.append("timestamp is empty")

    # Price positivity checks.
    for field in ("bid", "ask", "last_price"):
        val = getattr(tick, field)
        if val is not None and val <= 0:
            errors.append(f"{field} must be > 0, got {val}")

    if tick.volume_24h is not None and tick.volume_24h < 0:
        errors.append(f"volume_24h must be >= 0, got {tick.volume_24h}")

    # Bid < ask check.
    if tick.bid is not None and tick.ask is not None and tick.bid >= tick.ask:
        errors.append(f"bid ({tick.bid}) must be < ask ({tick.ask})")

    # Timestamp not in future (with 60s tolerance).
    if tick.timestamp:
        try:
            ts = datetime.fromisoformat(tick.timestamp.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            if ts > now.replace(second=now.second + 60 if now.second < 60 else 59):
                errors.append(f"timestamp {tick.timestamp} is in the future")
        except (ValueError, TypeError):
            pass  # Non-parseable timestamps are allowed through.

    return errors


def normalize_binance(
    raw: Dict[str, Any], symbol_map: Optional[Dict[str, str]] = None
) -> NormalizedTick:
    """Normalize a Binance-style ticker payload.

    Expected fields: s (symbol), E (event time ms), b (best bid), a (best ask),
    c (last price), v (24h volume), w (vwap).
    """
    smap = symbol_map or DEFAULT_SYMBOL_MAP
    exchange = "binance"
    symbol = _resolve_symbol(raw.get("s", ""), smap)
    timestamp = _parse_timestamp(raw.get("E"))

    missing = []
    for key, label in [("b", "bid"), ("a", "ask"), ("c", "last_price")]:
        if key not in raw or raw[key] is None:
            missing.append(label)
    if missing:
        logger.warning("Binance payload missing fields: %s", missing)

    return NormalizedTick(
        symbol=symbol,
        exchange=exchange,
        timestamp=timestamp or "",
        bid=_safe_float(raw.get("b"), "bid", exchange),
        ask=_safe_float(raw.get("a"), "ask", exchange),
        last_price=_safe_float(raw.get("c"), "last_price", exchange),
        volume_24h=_safe_float(raw.get("v"), "volume_24h", exchange),
        vwap=_safe_float(raw.get("w"), "vwap", exchange),
    )


def normalize_coinbase(
    raw: Dict[str, Any], symbol_map: Optional[Dict[str, str]] = None
) -> NormalizedTick:
    """Normalize a Coinbase-style ticker payload.

    Expected fields: product_id (e.g. BTC-USD), time (ISO-8601),
    best_bid, best_ask, price, volume_24h.
    """
    smap = symbol_map or DEFAULT_SYMBOL_MAP
    exchange = "coinbase"
    symbol = _resolve_symbol(raw.get("product_id", ""), smap)
    timestamp = raw.get("time", "")

    missing = []
    for key, label in [
        ("best_bid", "bid"),
        ("best_ask", "ask"),
        ("price", "last_price"),
    ]:
        if key not in raw or raw[key] is None:
            missing.append(label)
    if missing:
        logger.warning("Coinbase payload missing fields: %s", missing)

    return NormalizedTick(
        symbol=symbol,
        exchange=exchange,
        timestamp=timestamp,
        bid=_safe_float(raw.get("best_bid"), "bid", exchange),
        ask=_safe_float(raw.get("best_ask"), "ask", exchange),
        last_price=_safe_float(raw.get("price"), "last_price", exchange),
        volume_24h=_safe_float(raw.get("volume_24h"), "volume_24h", exchange),
        vwap=None,  # Coinbase ticker doesn't include VWAP.
    )


def normalize_alpaca(
    raw: Dict[str, Any], symbol_map: Optional[Dict[str, str]] = None
) -> NormalizedTick:
    """Normalize an Alpaca-style quote/trade payload.

    Expected fields: S (symbol, e.g. BTC/USD), t (ISO-8601 timestamp),
    bp (bid price), ap (ask price), p (last trade price), v (volume),
    vw (vwap).
    """
    smap = symbol_map or DEFAULT_SYMBOL_MAP
    exchange = "alpaca"
    symbol = _resolve_symbol(raw.get("S", ""), smap)
    timestamp = raw.get("t", "")

    missing = []
    for key, label in [("bp", "bid"), ("ap", "ask"), ("p", "last_price")]:
        if key not in raw or raw[key] is None:
            missing.append(label)
    if missing:
        logger.warning("Alpaca payload missing fields: %s", missing)

    return NormalizedTick(
        symbol=symbol,
        exchange=exchange,
        timestamp=timestamp,
        bid=_safe_float(raw.get("bp"), "bid", exchange),
        ask=_safe_float(raw.get("ap"), "ask", exchange),
        last_price=_safe_float(raw.get("p"), "last_price", exchange),
        volume_24h=_safe_float(raw.get("v"), "volume_24h", exchange),
        vwap=_safe_float(raw.get("vw"), "vwap", exchange),
    )


# Exchange name -> normalizer function.
EXCHANGE_NORMALIZERS = {
    "binance": normalize_binance,
    "coinbase": normalize_coinbase,
    "alpaca": normalize_alpaca,
}


def normalize(
    raw: Dict[str, Any],
    exchange: str,
    symbol_map: Optional[Dict[str, str]] = None,
) -> NormalizedTick:
    """Normalize a raw market data payload from a named exchange.

    Args:
        raw: Raw payload dict from the exchange.
        exchange: Exchange identifier (binance, coinbase, alpaca).
        symbol_map: Optional custom symbol mapping overrides.

    Returns:
        NormalizedTick with unified fields.

    Raises:
        ValueError: If exchange is not supported.
    """
    normalizer = EXCHANGE_NORMALIZERS.get(exchange.lower())
    if normalizer is None:
        raise ValueError(
            f"Unsupported exchange: {exchange}. "
            f"Supported: {list(EXCHANGE_NORMALIZERS)}"
        )
    return normalizer(raw, symbol_map)
