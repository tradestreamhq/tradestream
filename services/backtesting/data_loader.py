"""
Data loader for the backtesting engine.

Reads historical candle data from InfluxDB for use in backtesting.
Wraps the existing InfluxDBMarketClient to provide a DataFrame-oriented
interface suitable for the backtesting engine.
"""

from typing import Dict, List, Optional

import pandas as pd

from services.market_mcp.influxdb_client import InfluxDBMarketClient


class BacktestDataLoader:
    """Loads historical market data from InfluxDB for backtesting."""

    def __init__(
        self,
        influxdb_url: str,
        influxdb_token: str,
        influxdb_org: str,
        influxdb_bucket: str,
    ):
        self._client = InfluxDBMarketClient(
            url=influxdb_url,
            token=influxdb_token,
            org=influxdb_org,
            bucket=influxdb_bucket,
        )
        self._connected = False

    def connect(self) -> None:
        """Establish connection to InfluxDB."""
        if not self._connected:
            self._client.connect()
            self._connected = True

    def close(self) -> None:
        """Close the InfluxDB connection."""
        if self._connected:
            self._client.close()
            self._connected = False

    def load_candles(
        self,
        symbol: str,
        start: str,
        end: Optional[str] = None,
        timeframe: str = "1m",
        limit: int = 100000,
    ) -> pd.DataFrame:
        """
        Load candle data for a single symbol.

        Args:
            symbol: Currency pair (e.g., "BTC/USD").
            start: Start time in RFC3339 format (e.g., "2024-01-01T00:00:00Z").
            end: End time in RFC3339 format. Defaults to now.
            timeframe: Candle interval (e.g., "1m", "5m", "1h", "1d").
            limit: Maximum number of candles to return.

        Returns:
            DataFrame with columns [open, high, low, close, volume]
            indexed by datetime.
        """
        self.connect()

        candles = self._client.get_candles(
            symbol=symbol,
            timeframe=timeframe,
            start=start,
            end=end,
            limit=limit,
        )

        return self._candles_to_dataframe(candles)

    def load_multiple_symbols(
        self,
        symbols: List[str],
        start: str,
        end: Optional[str] = None,
        timeframe: str = "1m",
        limit: int = 100000,
    ) -> Dict[str, pd.DataFrame]:
        """
        Load candle data for multiple symbols.

        Args:
            symbols: List of currency pairs.
            start: Start time in RFC3339 format.
            end: End time in RFC3339 format.
            timeframe: Candle interval.
            limit: Maximum candles per symbol.

        Returns:
            Dict mapping symbol to its OHLCV DataFrame.
        """
        result = {}
        for symbol in symbols:
            df = self.load_candles(
                symbol=symbol,
                start=start,
                end=end,
                timeframe=timeframe,
                limit=limit,
            )
            if not df.empty:
                result[symbol] = df
        return result

    @staticmethod
    def _candles_to_dataframe(candles: List[dict]) -> pd.DataFrame:
        """Convert a list of candle dicts to an OHLCV DataFrame."""
        if not candles:
            return pd.DataFrame(
                columns=["open", "high", "low", "close", "volume"]
            )

        df = pd.DataFrame(candles)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.set_index("timestamp").sort_index()
        df = df[["open", "high", "low", "close", "volume"]].astype(float)
        return df

    @staticmethod
    def from_dataframe(df: pd.DataFrame) -> pd.DataFrame:
        """
        Validate and normalize an in-memory DataFrame for backtesting.

        Useful for testing or when data is already loaded.

        Args:
            df: DataFrame that must contain open, high, low, close, volume columns.

        Returns:
            Validated OHLCV DataFrame.

        Raises:
            ValueError: If required columns are missing.
        """
        required = {"open", "high", "low", "close", "volume"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"Missing required columns: {missing}")
        return df[["open", "high", "low", "close", "volume"]].astype(float)
