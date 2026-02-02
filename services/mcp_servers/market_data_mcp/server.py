"""Market Data MCP Server implementation.

Provides tools for accessing candle data, prices, and volatility from InfluxDB.
"""

import os
import re
import time
import math
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from influxdb_client import InfluxDBClient
from influxdb_client.client.exceptions import InfluxDBError

from ..common.server import BaseMCPServer, MCPResponse
from ..common.errors import MCPError, ErrorCode
from ..common.cache import Cache
from ..common.pagination import paginate, PaginationResult


# Valid symbol pattern
SYMBOL_PATTERN = re.compile(r"^[A-Z0-9]{2,10}/[A-Z0-9]{2,10}$")

# Valid timeframes and their durations in seconds
TIMEFRAMES = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "1h": 3600,
    "4h": 14400,
    "1d": 86400,
}

# Timeframes for volatility calculation
VOLATILITY_TIMEFRAMES = {"1h", "4h", "1d"}


class MarketDataMCPServer(BaseMCPServer):
    """MCP server for market data access from InfluxDB."""

    def __init__(
        self,
        influxdb_url: str = None,
        influxdb_token: str = None,
        influxdb_org: str = None,
        influxdb_bucket: str = None,
    ):
        # Get config from environment or parameters
        self.influxdb_url = influxdb_url or os.environ.get(
            "INFLUXDB_URL", "http://localhost:8086"
        )
        self.influxdb_token = influxdb_token or os.environ.get("INFLUXDB_TOKEN", "")
        self.influxdb_org = influxdb_org or os.environ.get("INFLUXDB_ORG", "tradestream")
        self.influxdb_bucket = influxdb_bucket or os.environ.get(
            "INFLUXDB_BUCKET", "tradestream-data"
        )

        # Initialize InfluxDB client
        self.client = InfluxDBClient(
            url=self.influxdb_url,
            token=self.influxdb_token,
            org=self.influxdb_org,
        )
        self.query_api = self.client.query_api()

        # Initialize cache with different TTLs for different data types
        self.cache = Cache(default_ttl=60)

        super().__init__(name="market-data-mcp", version="1.0.0")

    def _setup_tools(self) -> None:
        """Register market data tools."""
        self.register_tool(
            name="get_candles",
            description="Fetch OHLCV candle data for a symbol",
            parameters={
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Trading pair e.g. ETH/USD"},
                    "timeframe": {
                        "type": "string",
                        "enum": list(TIMEFRAMES.keys()),
                        "default": "1h",
                    },
                    "limit": {"type": "integer", "default": 100, "maximum": 1000},
                    "offset": {"type": "integer", "default": 0},
                    "force_refresh": {"type": "boolean", "default": False},
                },
                "required": ["symbol"],
            },
            handler=self.get_candles,
        )

        self.register_tool(
            name="get_current_price",
            description="Get the current price and recent change for a symbol",
            parameters={
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Trading pair"},
                    "force_refresh": {"type": "boolean", "default": False},
                },
                "required": ["symbol"],
            },
            handler=self.get_current_price,
        )

        self.register_tool(
            name="get_volatility",
            description="Calculate volatility metrics for a symbol",
            parameters={
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Trading pair"},
                    "timeframe": {
                        "type": "string",
                        "enum": list(VOLATILITY_TIMEFRAMES),
                        "default": "1h",
                    },
                    "force_refresh": {"type": "boolean", "default": False},
                },
                "required": ["symbol"],
            },
            handler=self.get_volatility,
        )

    def _validate_symbol(self, symbol: str) -> None:
        """Validate symbol format."""
        if not symbol or not SYMBOL_PATTERN.match(symbol.upper()):
            raise MCPError(
                code=ErrorCode.INVALID_SYMBOL,
                message=f"Invalid symbol format: {symbol}. Expected format: XXX/YYY",
                details={"symbol": symbol},
            )

    def _validate_timeframe(self, timeframe: str, valid_set: set = None) -> None:
        """Validate timeframe parameter."""
        valid_set = valid_set or set(TIMEFRAMES.keys())
        if timeframe not in valid_set:
            raise MCPError(
                code=ErrorCode.INVALID_TIMEFRAME,
                message=f"Invalid timeframe: {timeframe}. Valid options: {', '.join(valid_set)}",
                details={"timeframe": timeframe, "valid_timeframes": list(valid_set)},
            )

    def _symbol_to_influx_tag(self, symbol: str) -> str:
        """Convert symbol format to InfluxDB tag format.

        InfluxDB stores currency_pair as 'BTC/USD' format.
        """
        return symbol.upper()

    def get_candles(
        self,
        symbol: str,
        timeframe: str = "1h",
        limit: int = 100,
        offset: int = 0,
        force_refresh: bool = False,
    ) -> MCPResponse:
        """Fetch OHLCV candle data."""
        start_time = time.time()

        # Validate inputs
        self._validate_symbol(symbol)
        self._validate_timeframe(timeframe)
        symbol = symbol.upper()

        # Check cache
        cache_key = self.cache._make_key("candles", symbol=symbol, timeframe=timeframe)
        if not force_refresh:
            entry = self.cache.get(cache_key)
            if entry:
                result = paginate(entry.value, offset=offset, limit=limit, max_limit=1000)
                return MCPResponse(
                    data=result.to_dict(),
                    latency_ms=int((time.time() - start_time) * 1000),
                    cached=True,
                    cache_ttl_remaining=entry.ttl_remaining,
                    source="cache",
                )

        try:
            # Calculate time range
            duration_seconds = TIMEFRAMES[timeframe]
            # Fetch more than limit to enable pagination from cache
            fetch_count = min(limit + offset + 100, 1000)
            range_seconds = duration_seconds * fetch_count

            # Build Flux query
            query = f'''
                from(bucket: "{self.influxdb_bucket}")
                    |> range(start: -{range_seconds}s)
                    |> filter(fn: (r) => r["_measurement"] == "candles")
                    |> filter(fn: (r) => r["currency_pair"] == "{self._symbol_to_influx_tag(symbol)}")
                    |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
                    |> sort(columns: ["_time"], desc: true)
                    |> limit(n: {fetch_count})
            '''

            tables = self.query_api.query(query)

            candles = []
            for table in tables:
                for record in table.records:
                    candles.append({
                        "timestamp": record.get_time().isoformat(),
                        "open": record.values.get("open"),
                        "high": record.values.get("high"),
                        "low": record.values.get("low"),
                        "close": record.values.get("close"),
                        "volume": record.values.get("volume"),
                    })

            if not candles:
                raise MCPError(
                    code=ErrorCode.NO_DATA,
                    message=f"No candle data available for {symbol}",
                    details={"symbol": symbol, "timeframe": timeframe},
                )

            # Cache full results
            self.cache.set(cache_key, candles, ttl=60)

            # Apply pagination
            result = paginate(candles, offset=offset, limit=limit, max_limit=1000)

            return MCPResponse(
                data=result.to_dict(),
                latency_ms=int((time.time() - start_time) * 1000),
                cached=False,
                source="influxdb",
            )

        except MCPError:
            raise
        except InfluxDBError as e:
            raise MCPError(
                code=ErrorCode.DATABASE_ERROR,
                message=f"InfluxDB error: {str(e)}",
            )
        except Exception as e:
            raise MCPError(
                code=ErrorCode.DATABASE_ERROR,
                message=f"Database error: {str(e)}",
            )

    def get_current_price(
        self,
        symbol: str,
        force_refresh: bool = False,
    ) -> MCPResponse:
        """Get current price and recent changes."""
        start_time = time.time()

        # Validate inputs
        self._validate_symbol(symbol)
        symbol = symbol.upper()

        # Check cache (short TTL for price data)
        cache_key = self.cache._make_key("current_price", symbol=symbol)
        if not force_refresh:
            entry = self.cache.get(cache_key)
            if entry:
                return MCPResponse(
                    data=entry.value,
                    latency_ms=int((time.time() - start_time) * 1000),
                    cached=True,
                    cache_ttl_remaining=entry.ttl_remaining,
                    source="cache",
                )

        try:
            # Get latest candle
            query = f'''
                from(bucket: "{self.influxdb_bucket}")
                    |> range(start: -25h)
                    |> filter(fn: (r) => r["_measurement"] == "candles")
                    |> filter(fn: (r) => r["currency_pair"] == "{self._symbol_to_influx_tag(symbol)}")
                    |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
                    |> sort(columns: ["_time"], desc: true)
                    |> limit(n: 25)
            '''

            tables = self.query_api.query(query)

            candles = []
            for table in tables:
                for record in table.records:
                    candles.append({
                        "timestamp": record.get_time(),
                        "close": record.values.get("close"),
                        "volume": record.values.get("volume"),
                    })

            if not candles:
                raise MCPError(
                    code=ErrorCode.SYMBOL_NOT_FOUND,
                    message=f"No price data available for {symbol}",
                    details={"symbol": symbol},
                )

            # Calculate changes
            current_price = candles[0]["close"]
            current_timestamp = candles[0]["timestamp"]

            # Find price 1 hour ago and 24 hours ago
            price_1h = current_price
            price_24h = current_price
            volume_24h = 0.0

            for candle in candles:
                age = (current_timestamp - candle["timestamp"]).total_seconds()
                volume_24h += candle["volume"] or 0

                if age >= 3600 and price_1h == current_price:
                    price_1h = candle["close"]
                if age >= 86400:
                    price_24h = candle["close"]
                    break

            change_1h = ((current_price - price_1h) / price_1h * 100) if price_1h else 0
            change_24h = ((current_price - price_24h) / price_24h * 100) if price_24h else 0

            result = {
                "price": current_price,
                "change_1h": round(change_1h, 4),
                "change_24h": round(change_24h, 4),
                "volume_24h": volume_24h,
                "timestamp": current_timestamp.isoformat(),
            }

            # Cache with short TTL
            self.cache.set(cache_key, result, ttl=5)

            return MCPResponse(
                data=result,
                latency_ms=int((time.time() - start_time) * 1000),
                cached=False,
                source="influxdb",
            )

        except MCPError:
            raise
        except InfluxDBError as e:
            raise MCPError(
                code=ErrorCode.DATABASE_ERROR,
                message=f"InfluxDB error: {str(e)}",
            )
        except Exception as e:
            raise MCPError(
                code=ErrorCode.DATABASE_ERROR,
                message=f"Database error: {str(e)}",
            )

    def get_volatility(
        self,
        symbol: str,
        timeframe: str = "1h",
        force_refresh: bool = False,
    ) -> MCPResponse:
        """Calculate volatility metrics."""
        start_time = time.time()

        # Validate inputs
        self._validate_symbol(symbol)
        self._validate_timeframe(timeframe, VOLATILITY_TIMEFRAMES)
        symbol = symbol.upper()

        # Check cache
        cache_key = self.cache._make_key("volatility", symbol=symbol, timeframe=timeframe)
        if not force_refresh:
            entry = self.cache.get(cache_key)
            if entry:
                return MCPResponse(
                    data=entry.value,
                    latency_ms=int((time.time() - start_time) * 1000),
                    cached=True,
                    cache_ttl_remaining=entry.ttl_remaining,
                    source="cache",
                )

        try:
            # Determine lookback period based on timeframe
            periods_needed = 20  # Typical ATR period
            duration_seconds = TIMEFRAMES[timeframe]
            range_seconds = duration_seconds * (periods_needed + 5)

            query = f'''
                from(bucket: "{self.influxdb_bucket}")
                    |> range(start: -{range_seconds}s)
                    |> filter(fn: (r) => r["_measurement"] == "candles")
                    |> filter(fn: (r) => r["currency_pair"] == "{self._symbol_to_influx_tag(symbol)}")
                    |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
                    |> sort(columns: ["_time"], desc: true)
                    |> limit(n: {periods_needed + 5})
            '''

            tables = self.query_api.query(query)

            candles = []
            for table in tables:
                for record in table.records:
                    candles.append({
                        "high": record.values.get("high"),
                        "low": record.values.get("low"),
                        "close": record.values.get("close"),
                    })

            if len(candles) < 5:
                raise MCPError(
                    code=ErrorCode.INSUFFICIENT_DATA,
                    message=f"Insufficient data to calculate volatility for {symbol}",
                    details={"symbol": symbol, "available_candles": len(candles)},
                )

            # Calculate returns for volatility
            returns = []
            for i in range(1, len(candles)):
                if candles[i]["close"] and candles[i - 1]["close"]:
                    ret = (candles[i - 1]["close"] - candles[i]["close"]) / candles[i]["close"]
                    returns.append(ret)

            # Standard deviation of returns
            if returns:
                mean_return = sum(returns) / len(returns)
                variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
                volatility = math.sqrt(variance)
            else:
                volatility = 0

            # Calculate ATR
            true_ranges = []
            for i in range(1, len(candles)):
                if all([candles[i]["high"], candles[i]["low"], candles[i - 1]["close"]]):
                    high_low = candles[i]["high"] - candles[i]["low"]
                    high_close = abs(candles[i]["high"] - candles[i - 1]["close"])
                    low_close = abs(candles[i]["low"] - candles[i - 1]["close"])
                    true_ranges.append(max(high_low, high_close, low_close))

            atr = sum(true_ranges) / len(true_ranges) if true_ranges else 0

            # High-low range (percentage)
            if candles and candles[0]["low"]:
                high_low_range = (candles[0]["high"] - candles[0]["low"]) / candles[0]["low"] * 100
            else:
                high_low_range = 0

            result = {
                "volatility": round(volatility, 6),
                "atr": round(atr, 6),
                "high_low_range": round(high_low_range, 4),
            }

            # Cache volatility data
            self.cache.set(cache_key, result, ttl=30)

            return MCPResponse(
                data=result,
                latency_ms=int((time.time() - start_time) * 1000),
                cached=False,
                source="influxdb",
            )

        except MCPError:
            raise
        except InfluxDBError as e:
            raise MCPError(
                code=ErrorCode.DATABASE_ERROR,
                message=f"InfluxDB error: {str(e)}",
            )
        except Exception as e:
            raise MCPError(
                code=ErrorCode.DATABASE_ERROR,
                message=f"Database error: {str(e)}",
            )

    def close(self) -> None:
        """Close the InfluxDB client."""
        if self.client:
            self.client.close()


def main():
    """Run the market data MCP server."""
    server = MarketDataMCPServer()
    try:
        server.run_stdio()
    finally:
        server.close()


if __name__ == "__main__":
    main()
