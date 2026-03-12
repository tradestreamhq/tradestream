"""Tests for backtesting data loader."""

from unittest import mock

import pandas as pd
import pytest

from services.backtesting.data_loader import BacktestDataLoader


@pytest.fixture
def sample_candles():
    """Sample candle data as returned by InfluxDB client."""
    return [
        {
            "timestamp": "2024-01-01T00:00:00+00:00",
            "open": 100.0,
            "high": 102.0,
            "low": 99.0,
            "close": 101.0,
            "volume": 1000.0,
        },
        {
            "timestamp": "2024-01-01T00:01:00+00:00",
            "open": 101.0,
            "high": 103.0,
            "low": 100.0,
            "close": 102.5,
            "volume": 1200.0,
        },
        {
            "timestamp": "2024-01-01T00:02:00+00:00",
            "open": 102.5,
            "high": 104.0,
            "low": 101.5,
            "close": 103.0,
            "volume": 800.0,
        },
    ]


class TestCandlesToDataframe:
    def test_converts_candles(self, sample_candles):
        df = BacktestDataLoader._candles_to_dataframe(sample_candles)
        assert len(df) == 3
        assert list(df.columns) == ["open", "high", "low", "close", "volume"]
        assert df.index.name == "timestamp"
        assert df["close"].iloc[0] == 101.0

    def test_empty_candles(self):
        df = BacktestDataLoader._candles_to_dataframe([])
        assert df.empty
        assert list(df.columns) == ["open", "high", "low", "close", "volume"]

    def test_sorted_by_timestamp(self):
        candles = [
            {"timestamp": "2024-01-01T00:02:00+00:00", "open": 3, "high": 3, "low": 3, "close": 3, "volume": 100},
            {"timestamp": "2024-01-01T00:00:00+00:00", "open": 1, "high": 1, "low": 1, "close": 1, "volume": 100},
            {"timestamp": "2024-01-01T00:01:00+00:00", "open": 2, "high": 2, "low": 2, "close": 2, "volume": 100},
        ]
        df = BacktestDataLoader._candles_to_dataframe(candles)
        assert df["close"].tolist() == [1.0, 2.0, 3.0]


class TestFromDataframe:
    def test_valid_dataframe(self):
        df = pd.DataFrame({
            "open": [100.0],
            "high": [102.0],
            "low": [99.0],
            "close": [101.0],
            "volume": [1000.0],
            "extra_col": ["ignored"],
        })
        result = BacktestDataLoader.from_dataframe(df)
        assert list(result.columns) == ["open", "high", "low", "close", "volume"]
        assert "extra_col" not in result.columns

    def test_missing_columns(self):
        df = pd.DataFrame({"open": [100.0], "close": [101.0]})
        with pytest.raises(ValueError, match="Missing required columns"):
            BacktestDataLoader.from_dataframe(df)


class TestLoadCandles:
    @mock.patch("services.backtesting.data_loader.InfluxDBMarketClient")
    def test_load_candles(self, mock_client_cls, sample_candles):
        mock_client = mock.MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.get_candles.return_value = sample_candles

        loader = BacktestDataLoader("http://localhost:8086", "token", "org", "bucket")
        df = loader.load_candles("BTC/USD", start="2024-01-01T00:00:00Z")

        mock_client.connect.assert_called_once()
        mock_client.get_candles.assert_called_once_with(
            symbol="BTC/USD",
            timeframe="1m",
            start="2024-01-01T00:00:00Z",
            end=None,
            limit=100000,
        )
        assert len(df) == 3

    @mock.patch("services.backtesting.data_loader.InfluxDBMarketClient")
    def test_load_multiple_symbols(self, mock_client_cls, sample_candles):
        mock_client = mock.MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.get_candles.return_value = sample_candles

        loader = BacktestDataLoader("http://localhost:8086", "token", "org", "bucket")
        result = loader.load_multiple_symbols(
            ["BTC/USD", "ETH/USD"],
            start="2024-01-01T00:00:00Z",
        )

        assert len(result) == 2
        assert "BTC/USD" in result
        assert "ETH/USD" in result
        assert mock_client.get_candles.call_count == 2

    @mock.patch("services.backtesting.data_loader.InfluxDBMarketClient")
    def test_skips_empty_symbols(self, mock_client_cls):
        mock_client = mock.MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.get_candles.return_value = []

        loader = BacktestDataLoader("http://localhost:8086", "token", "org", "bucket")
        result = loader.load_multiple_symbols(
            ["BTC/USD"],
            start="2024-01-01T00:00:00Z",
        )

        assert len(result) == 0

    @mock.patch("services.backtesting.data_loader.InfluxDBMarketClient")
    def test_close(self, mock_client_cls):
        mock_client = mock.MagicMock()
        mock_client_cls.return_value = mock_client

        loader = BacktestDataLoader("http://localhost:8086", "token", "org", "bucket")
        loader.connect()
        loader.close()

        mock_client.close.assert_called_once()

    @mock.patch("services.backtesting.data_loader.InfluxDBMarketClient")
    def test_connect_once(self, mock_client_cls):
        mock_client = mock.MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.get_candles.return_value = []

        loader = BacktestDataLoader("http://localhost:8086", "token", "org", "bucket")
        loader.load_candles("BTC/USD", start="2024-01-01T00:00:00Z")
        loader.load_candles("ETH/USD", start="2024-01-01T00:00:00Z")

        # Should only connect once
        mock_client.connect.assert_called_once()
