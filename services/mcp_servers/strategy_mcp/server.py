"""Strategy MCP Server implementation.

Provides tools for accessing strategy performance data and signals from PostgreSQL.
"""

import os
import re
import time
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras
import psycopg2.pool

from ..common.server import BaseMCPServer, MCPResponse
from ..common.errors import MCPError, ErrorCode
from ..common.cache import Cache
from ..common.pagination import paginate, PaginationResult


# Valid symbol pattern (e.g., BTC/USD, ETH/USDT)
SYMBOL_PATTERN = re.compile(r"^[A-Z0-9]{2,10}/[A-Z0-9]{2,10}$")

# Valid metrics for sorting
VALID_METRICS = {"sharpe", "accuracy", "return"}


class StrategyMCPServer(BaseMCPServer):
    """MCP server for strategy data access."""

    def __init__(
        self,
        postgres_host: str = None,
        postgres_port: int = None,
        postgres_database: str = None,
        postgres_user: str = None,
        postgres_password: str = None,
    ):
        # Get config from environment or parameters
        self.postgres_host = postgres_host or os.environ.get(
            "POSTGRES_HOST", "localhost"
        )
        self.postgres_port = postgres_port or int(
            os.environ.get("POSTGRES_PORT", "5432")
        )
        self.postgres_database = postgres_database or os.environ.get(
            "POSTGRES_DATABASE", "tradestream"
        )
        self.postgres_user = postgres_user or os.environ.get(
            "POSTGRES_USERNAME", "postgres"
        )
        self.postgres_password = postgres_password or os.environ.get(
            "POSTGRES_PASSWORD", ""
        )

        # Initialize connection pool
        self.pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=2,
            maxconn=10,
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_database,
            user=self.postgres_user,
            password=self.postgres_password,
        )

        # Initialize cache
        self.cache = Cache(default_ttl=30)

        super().__init__(name="strategy-mcp", version="1.0.0")

    def _setup_tools(self) -> None:
        """Register strategy tools."""
        self.register_tool(
            name="get_top_strategies",
            description="Fetch top N strategies for a symbol ranked by performance score",
            parameters={
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Trading pair e.g. ETH/USD",
                    },
                    "limit": {"type": "integer", "default": 5, "maximum": 100},
                    "offset": {"type": "integer", "default": 0},
                    "metric": {
                        "type": "string",
                        "enum": ["sharpe", "accuracy", "return"],
                        "default": "sharpe",
                    },
                    "force_refresh": {"type": "boolean", "default": False},
                },
                "required": ["symbol"],
            },
            handler=self.get_top_strategies,
        )

        self.register_tool(
            name="get_strategy_signal",
            description="Get the current signal from a specific strategy for a symbol",
            parameters={
                "type": "object",
                "properties": {
                    "strategy_id": {
                        "type": "string",
                        "description": "Strategy identifier",
                    },
                    "symbol": {"type": "string", "description": "Trading pair"},
                    "force_refresh": {"type": "boolean", "default": False},
                },
                "required": ["strategy_id", "symbol"],
            },
            handler=self.get_strategy_signal,
        )

        self.register_tool(
            name="get_strategy_consensus",
            description="Get aggregated consensus across all active strategies for a symbol",
            parameters={
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Trading pair"},
                    "force_refresh": {"type": "boolean", "default": False},
                },
                "required": ["symbol"],
            },
            handler=self.get_strategy_consensus,
        )

    def _validate_symbol(self, symbol: str) -> None:
        """Validate symbol format."""
        if not symbol or not SYMBOL_PATTERN.match(symbol.upper()):
            raise MCPError(
                code=ErrorCode.INVALID_SYMBOL,
                message=f"Invalid symbol format: {symbol}. Expected format: XXX/YYY",
                details={"symbol": symbol},
            )

    def _validate_metric(self, metric: str) -> None:
        """Validate metric parameter."""
        if metric not in VALID_METRICS:
            raise MCPError(
                code=ErrorCode.INVALID_METRIC,
                message=f"Invalid metric: {metric}. Valid options: {', '.join(VALID_METRICS)}",
                details={"metric": metric, "valid_metrics": list(VALID_METRICS)},
            )

    def _get_connection(self):
        """Get a connection from the pool."""
        return self.pool.getconn()

    def _release_connection(self, conn):
        """Release a connection back to the pool."""
        self.pool.putconn(conn)

    def get_top_strategies(
        self,
        symbol: str,
        limit: int = 5,
        offset: int = 0,
        metric: str = "sharpe",
        force_refresh: bool = False,
    ) -> MCPResponse:
        """Fetch top strategies for a symbol."""
        start_time = time.time()

        # Validate inputs
        self._validate_symbol(symbol)
        self._validate_metric(metric)
        symbol = symbol.upper()

        # Check cache
        cache_key = self.cache._make_key("top_strategies", symbol=symbol, metric=metric)
        if not force_refresh:
            entry = self.cache.get(cache_key)
            if entry:
                # Apply pagination to cached results
                result = paginate(
                    entry.value, offset=offset, limit=limit, max_limit=100
                )
                return MCPResponse(
                    data=result.to_dict(),
                    latency_ms=int((time.time() - start_time) * 1000),
                    cached=True,
                    cache_ttl_remaining=entry.ttl_remaining,
                    source="cache",
                )

        # Query database
        conn = self._get_connection()
        try:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

            # Map metric to column
            order_column = {
                "sharpe": "current_score",  # Using current_score as proxy for Sharpe
                "accuracy": "current_score",
                "return": "current_score",
            }.get(metric, "current_score")

            query = """
                SELECT
                    strategy_id::text,
                    strategy_type as name,
                    current_score as score,
                    current_score as sharpe,
                    current_score as accuracy,
                    0 as signals_count
                FROM strategies
                WHERE symbol = %s AND is_active = TRUE
                ORDER BY {} DESC
            """.format(
                order_column
            )

            cursor.execute(query, (symbol,))
            rows = cursor.fetchall()

            if not rows:
                raise MCPError(
                    code=ErrorCode.SYMBOL_NOT_FOUND,
                    message=f"No strategies found for symbol: {symbol}",
                    details={"symbol": symbol},
                )

            # Convert to list of dicts
            strategies = [dict(row) for row in rows]

            # Cache full results
            self.cache.set(cache_key, strategies, ttl=30)

            # Apply pagination
            result = paginate(strategies, offset=offset, limit=limit, max_limit=100)

            return MCPResponse(
                data=result.to_dict(),
                latency_ms=int((time.time() - start_time) * 1000),
                cached=False,
                source="postgresql",
            )

        except MCPError:
            raise
        except Exception as e:
            raise MCPError(
                code=ErrorCode.DATABASE_ERROR,
                message=f"Database error: {str(e)}",
            )
        finally:
            self._release_connection(conn)

    def get_strategy_signal(
        self,
        strategy_id: str,
        symbol: str,
        force_refresh: bool = False,
    ) -> MCPResponse:
        """Get current signal from a strategy."""
        start_time = time.time()

        # Validate inputs
        self._validate_symbol(symbol)
        symbol = symbol.upper()

        # Check cache
        cache_key = self.cache._make_key(
            "strategy_signal", strategy_id=strategy_id, symbol=symbol
        )
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

        conn = self._get_connection()
        try:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

            # First verify strategy exists
            cursor.execute(
                "SELECT strategy_id, current_score, parameters FROM strategies WHERE strategy_id = %s::uuid AND symbol = %s",
                (strategy_id, symbol),
            )
            strategy = cursor.fetchone()

            if not strategy:
                raise MCPError(
                    code=ErrorCode.STRATEGY_NOT_FOUND,
                    message=f"Strategy not found: {strategy_id}",
                    details={"strategy_id": strategy_id, "symbol": symbol},
                )

            # For now, generate a signal based on score
            # In production, this would query a signals table
            score = float(strategy["current_score"])
            if score > 0.7:
                signal = "BUY"
                confidence = min(score, 0.95)
            elif score < 0.3:
                signal = "SELL"
                confidence = min(1 - score, 0.95)
            else:
                signal = "HOLD"
                confidence = 0.5

            result = {
                "signal": signal,
                "confidence": round(confidence, 4),
                "triggered_at": None,  # Would come from signals table
                "parameters": strategy.get("parameters", {}),
            }

            # Cache with shorter TTL for signals
            self.cache.set(cache_key, result, ttl=10)

            return MCPResponse(
                data=result,
                latency_ms=int((time.time() - start_time) * 1000),
                cached=False,
                source="postgresql",
            )

        except MCPError:
            raise
        except Exception as e:
            raise MCPError(
                code=ErrorCode.DATABASE_ERROR,
                message=f"Database error: {str(e)}",
            )
        finally:
            self._release_connection(conn)

    def get_strategy_consensus(
        self,
        symbol: str,
        force_refresh: bool = False,
    ) -> MCPResponse:
        """Get aggregated consensus across strategies."""
        start_time = time.time()

        # Validate inputs
        self._validate_symbol(symbol)
        symbol = symbol.upper()

        # Check cache
        cache_key = self.cache._make_key("strategy_consensus", symbol=symbol)
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

        conn = self._get_connection()
        try:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

            # Get all active strategies for the symbol
            cursor.execute(
                """
                SELECT current_score
                FROM strategies
                WHERE symbol = %s AND is_active = TRUE
                """,
                (symbol,),
            )
            rows = cursor.fetchall()

            if not rows:
                raise MCPError(
                    code=ErrorCode.NO_ACTIVE_STRATEGIES,
                    message=f"No active strategies found for symbol: {symbol}",
                    details={"symbol": symbol},
                )

            # Calculate consensus based on scores
            bullish_count = 0
            bearish_count = 0
            neutral_count = 0

            for row in rows:
                score = float(row["current_score"])
                if score > 0.6:
                    bullish_count += 1
                elif score < 0.4:
                    bearish_count += 1
                else:
                    neutral_count += 1

            total = bullish_count + bearish_count + neutral_count
            bullish_pct = bullish_count / total if total > 0 else 0
            bearish_pct = bearish_count / total if total > 0 else 0

            # Determine consensus
            if bullish_pct >= 0.7:
                consensus = "STRONG_BUY"
                confidence = bullish_pct
            elif bullish_pct >= 0.5:
                consensus = "BUY"
                confidence = bullish_pct
            elif bearish_pct >= 0.7:
                consensus = "STRONG_SELL"
                confidence = bearish_pct
            elif bearish_pct >= 0.5:
                consensus = "SELL"
                confidence = bearish_pct
            else:
                consensus = "NEUTRAL"
                confidence = 1 - abs(bullish_pct - bearish_pct)

            result = {
                "bullish_count": bullish_count,
                "bearish_count": bearish_count,
                "neutral_count": neutral_count,
                "consensus": consensus,
                "confidence": round(confidence, 4),
            }

            # Cache with 30s TTL
            self.cache.set(cache_key, result, ttl=30)

            return MCPResponse(
                data=result,
                latency_ms=int((time.time() - start_time) * 1000),
                cached=False,
                source="postgresql",
            )

        except MCPError:
            raise
        except Exception as e:
            raise MCPError(
                code=ErrorCode.DATABASE_ERROR,
                message=f"Database error: {str(e)}",
            )
        finally:
            self._release_connection(conn)

    def close(self) -> None:
        """Close the connection pool."""
        if self.pool:
            self.pool.closeall()


def main():
    """Run the strategy MCP server."""
    server = StrategyMCPServer()
    try:
        server.run_stdio()
    finally:
        server.close()


if __name__ == "__main__":
    main()
