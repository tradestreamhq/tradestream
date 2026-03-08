"""MCP server exposing market data tools."""

import math
import statistics

from absl import logging
from mcp.server.fastmcp import FastMCP

from services.market_mcp.influxdb_client import InfluxDBQueryClient
from services.market_mcp.redis_client import RedisMarketClient

mcp = FastMCP("market-mcp")

# Module-level clients, initialized by init_server().
_influx_client: InfluxDBQueryClient | None = None
_redis_client: RedisMarketClient | None = None


def init_server(
    influx_client: InfluxDBQueryClient,
    redis_client: RedisMarketClient,
):
    global _influx_client, _redis_client
    _influx_client = influx_client
    _redis_client = redis_client


@mcp.tool()
def get_candles(
    symbol: str,
    timeframe: str = "1m",
    start: str | None = None,
    end: str | None = None,
    limit: int = 100,
) -> list[dict]:
    """Get OHLCV candle data for a symbol.

    Args:
        symbol: Currency pair (e.g. "BTC/USD").
        timeframe: Candle timeframe (e.g. "1m", "5m", "1h").
        start: Start time in RFC3339 or relative (e.g. "-1h").
        end: End time in RFC3339 or relative.
        limit: Maximum number of candles to return (default 100).

    Returns:
        List of candle dicts with timestamp, open, high, low, close, volume.
    """
    if not _influx_client:
        return [{"error": "InfluxDB client not initialized"}]
    return _influx_client.get_candles(symbol, timeframe, start, end, limit)


@mcp.tool()
def get_latest_price(symbol: str) -> dict:
    """Get the latest price for a symbol.

    Args:
        symbol: Currency pair (e.g. "BTC/USD").

    Returns:
        Dict with symbol, price, volume_24h, change_24h, timestamp.
    """
    if not _influx_client:
        return {"error": "InfluxDB client not initialized"}

    latest = _influx_client.get_latest_candle(symbol)
    if not latest:
        return {"error": f"No data found for {symbol}"}

    # Get 24h candles for volume and change calculation
    candles_24h = _influx_client.get_candles_for_24h(symbol)

    volume_24h = sum(c.get("volume", 0) or 0 for c in candles_24h)
    change_24h = 0.0
    if candles_24h and len(candles_24h) > 1:
        oldest = candles_24h[-1]
        if oldest.get("close") and oldest["close"] != 0:
            change_24h = (
                (latest["close"] - oldest["close"]) / oldest["close"]
            ) * 100

    return {
        "symbol": symbol,
        "price": latest.get("close"),
        "volume_24h": volume_24h,
        "change_24h": round(change_24h, 4),
        "timestamp": latest.get("timestamp"),
    }


@mcp.tool()
def get_volatility(symbol: str, period_minutes: int = 60) -> dict:
    """Compute volatility metrics for a symbol.

    Args:
        symbol: Currency pair (e.g. "BTC/USD").
        period_minutes: Lookback period in minutes (default 60).

    Returns:
        Dict with symbol, volatility (stddev of returns), atr, period.
    """
    if not _influx_client:
        return {"error": "InfluxDB client not initialized"}

    candles = _influx_client.get_candles_for_period(symbol, period_minutes)
    if not candles or len(candles) < 2:
        return {"error": f"Insufficient data for {symbol}"}

    # Sort by timestamp ascending for correct return calculation
    candles.sort(key=lambda c: c.get("timestamp", ""))

    # Calculate returns
    returns = []
    for i in range(1, len(candles)):
        prev_close = candles[i - 1].get("close")
        curr_close = candles[i].get("close")
        if prev_close and curr_close and prev_close != 0:
            returns.append((curr_close - prev_close) / prev_close)

    volatility = statistics.stdev(returns) if len(returns) >= 2 else 0.0

    # Calculate ATR (Average True Range)
    true_ranges = []
    for i in range(1, len(candles)):
        high = candles[i].get("high", 0) or 0
        low = candles[i].get("low", 0) or 0
        prev_close = candles[i - 1].get("close", 0) or 0
        tr = max(
            high - low,
            abs(high - prev_close),
            abs(low - prev_close),
        )
        true_ranges.append(tr)

    atr = statistics.mean(true_ranges) if true_ranges else 0.0

    return {
        "symbol": symbol,
        "volatility": round(volatility, 8),
        "atr": round(atr, 4),
        "period": period_minutes,
    }


@mcp.tool()
def get_symbols() -> list[dict]:
    """Get all tracked cryptocurrency symbols.

    Returns:
        List of dicts with id, asset_class, base, quote, exchange.
    """
    if not _redis_client:
        return [{"error": "Redis client not initialized"}]
    return _redis_client.get_symbols()


@mcp.tool()
def get_market_summary(symbol: str) -> dict:
    """Get a comprehensive market summary for a symbol.

    Args:
        symbol: Currency pair (e.g. "BTC/USD").

    Returns:
        Dict with price, change_1h, change_24h, volume_24h, volatility,
        high_24h, low_24h, vwap.
    """
    if not _influx_client:
        return {"error": "InfluxDB client not initialized"}

    # Get 24h candles
    candles_24h = _influx_client.get_candles_for_24h(symbol)
    if not candles_24h:
        return {"error": f"No data found for {symbol}"}

    # Sort ascending
    candles_24h.sort(key=lambda c: c.get("timestamp", ""))

    latest = candles_24h[-1]
    price = latest.get("close", 0) or 0

    # 24h change
    oldest_24h = candles_24h[0]
    change_24h = 0.0
    if oldest_24h.get("close") and oldest_24h["close"] != 0:
        change_24h = ((price - oldest_24h["close"]) / oldest_24h["close"]) * 100

    # 1h change - use last 60 candles (1-minute candles)
    candles_1h = candles_24h[-60:] if len(candles_24h) >= 60 else candles_24h
    change_1h = 0.0
    if candles_1h and candles_1h[0].get("close") and candles_1h[0]["close"] != 0:
        change_1h = ((price - candles_1h[0]["close"]) / candles_1h[0]["close"]) * 100

    # Volume
    volume_24h = sum(c.get("volume", 0) or 0 for c in candles_24h)

    # High/Low
    highs = [c.get("high", 0) or 0 for c in candles_24h]
    lows = [c.get("low", 0) or 0 for c in candles_24h if c.get("low")]
    high_24h = max(highs) if highs else 0
    low_24h = min(lows) if lows else 0

    # VWAP (Volume Weighted Average Price)
    vwap_num = 0.0
    vwap_den = 0.0
    for c in candles_24h:
        typical_price = (
            (c.get("high", 0) or 0)
            + (c.get("low", 0) or 0)
            + (c.get("close", 0) or 0)
        ) / 3
        vol = c.get("volume", 0) or 0
        vwap_num += typical_price * vol
        vwap_den += vol
    vwap = vwap_num / vwap_den if vwap_den != 0 else 0.0

    # Volatility (stddev of returns)
    returns = []
    for i in range(1, len(candles_24h)):
        prev_close = candles_24h[i - 1].get("close")
        curr_close = candles_24h[i].get("close")
        if prev_close and curr_close and prev_close != 0:
            returns.append((curr_close - prev_close) / prev_close)
    volatility = statistics.stdev(returns) if len(returns) >= 2 else 0.0

    return {
        "symbol": symbol,
        "price": price,
        "change_1h": round(change_1h, 4),
        "change_24h": round(change_24h, 4),
        "volume_24h": volume_24h,
        "volatility": round(volatility, 8),
        "high_24h": high_24h,
        "low_24h": low_24h,
        "vwap": round(vwap, 4),
    }
