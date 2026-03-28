"""
Tests for the InfluxDB market client with mocked InfluxDB.
"""

import datetime
from unittest.mock import MagicMock, patch

import pytest

from services.market_mcp.influxdb_client import InfluxDBMarketClient


class TestInfluxDBMarketClient:
    """Test cases for InfluxDBMarketClient."""

    @pytest.fixture
    def client(self):
        """Create an InfluxDBMarketClient with a mocked connection."""
        c = InfluxDBMarketClient(
            url="http://localhost:8086",
            token="test-token",
            org="test-org",
            bucket="test-bucket",
        )
        c.client = MagicMock()
        return c

    def _make_record(self, values):
        """Create a mock record with given values."""
        record = MagicMock()
        record.values = values
        return record

    def _make_table(self, records):
        """Create a mock table with records."""
        table = MagicMock()
        table.records = [self._make_record(r) for r in records]
        return table

    def _mock_query(self, client, tables_data):
        """Set up the query_api mock to return tables."""
        tables = [self._make_table(records) for records in tables_data]
        client.client.query_api.return_value.query.return_value = tables

    def test_connect_success(self):
        """Test successful connection."""
        with patch("services.market_mcp.influxdb_client.InfluxDBClient") as mock_cls:
            mock_instance = MagicMock()
            mock_instance.ping.return_value = True
            mock_cls.return_value = mock_instance

            c = InfluxDBMarketClient(
                url="http://localhost:8086",
                token="tok",
                org="org",
                bucket="bucket",
            )
            c.connect()
            assert c.client is mock_instance

    def test_connect_failure(self):
        """Test connection failure raises."""
        with patch("services.market_mcp.influxdb_client.InfluxDBClient") as mock_cls:
            mock_instance = MagicMock()
            mock_instance.ping.return_value = False
            mock_cls.return_value = mock_instance

            c = InfluxDBMarketClient(
                url="http://localhost:8086",
                token="tok",
                org="org",
                bucket="bucket",
            )
            with pytest.raises(ConnectionError):
                c.connect()

    def test_query_without_connection(self):
        """Test querying without connecting raises RuntimeError."""
        c = InfluxDBMarketClient(
            url="http://localhost:8086",
            token="tok",
            org="org",
            bucket="bucket",
        )
        with pytest.raises(RuntimeError, match="not established"):
            c._query('from(bucket: "test")')

    def test_get_candles(self, client):
        """Test get_candles returns formatted OHLCV data."""
        ts = datetime.datetime(2026, 3, 8, 12, 0, 0)
        self._mock_query(
            client,
            [
                [
                    {
                        "_time": ts,
                        "open": 50000.0,
                        "high": 50100.0,
                        "low": 49900.0,
                        "close": 50050.0,
                        "volume": 1.5,
                    },
                    {
                        "_time": ts.replace(minute=1),
                        "open": 50050.0,
                        "high": 50200.0,
                        "low": 50000.0,
                        "close": 50150.0,
                        "volume": 2.0,
                    },
                ]
            ],
        )

        result = client.get_candles("BTC/USD", timeframe="1m", limit=100)

        assert len(result) == 2
        assert result[0]["open"] == 50000.0
        assert result[0]["close"] == 50050.0
        assert result[0]["volume"] == 1.5
        assert "timestamp" in result[0]
        assert result[1]["close"] == 50150.0

    def test_get_candles_empty(self, client):
        """Test get_candles with no data."""
        self._mock_query(client, [[]])
        result = client.get_candles("UNKNOWN/USD")
        assert result == []

    def test_get_candles_with_time_range(self, client):
        """Test get_candles with start and end parameters."""
        self._mock_query(client, [[]])
        client.get_candles("BTC/USD", start="-24h", end="-1h")
        query_call = client.client.query_api.return_value.query
        query_call.assert_called_once()
        flux = query_call.call_args[0][0]
        assert "-24h" in flux
        assert "-1h" in flux

    def test_get_latest_price(self, client):
        """Test get_latest_price returns correct structure."""
        ts = datetime.datetime(2026, 3, 8, 12, 0, 0)
        # First call: latest candle
        # Second call: 24h records
        call_count = [0]

        def side_effect(flux, org=None):
            call_count[0] += 1
            if call_count[0] == 1:
                # Latest candle
                return [
                    self._make_table(
                        [
                            {
                                "_time": ts,
                                "close": 50050.0,
                                "volume": 1.5,
                            }
                        ]
                    )
                ]
            else:
                # 24h records
                return [
                    self._make_table(
                        [
                            {
                                "_time": ts.replace(hour=0),
                                "close": 49000.0,
                                "volume": 10.0,
                            },
                            {"_time": ts, "close": 50050.0, "volume": 1.5},
                        ]
                    )
                ]

        client.client.query_api.return_value.query.side_effect = side_effect

        result = client.get_latest_price("BTC/USD")

        assert result["symbol"] == "BTC/USD"
        assert result["price"] == 50050.0
        assert result["volume_24h"] == 11.5
        assert result["change_24h"] is not None
        assert result["timestamp"] is not None

    def test_get_latest_price_no_data(self, client):
        """Test get_latest_price with no candle data."""
        self._mock_query(client, [[]])
        result = client.get_latest_price("UNKNOWN/USD")
        assert result["symbol"] == "UNKNOWN/USD"
        assert result["price"] is None

    def test_get_volatility(self, client):
        """Test get_volatility computes stddev and ATR."""
        records = [
            {"_time": "t0", "open": 100, "high": 105, "low": 95, "close": 100},
            {"_time": "t1", "open": 100, "high": 110, "low": 90, "close": 105},
            {"_time": "t2", "open": 105, "high": 115, "low": 100, "close": 110},
            {"_time": "t3", "open": 110, "high": 112, "low": 98, "close": 102},
        ]
        self._mock_query(client, [records])

        result = client.get_volatility("BTC/USD", period_minutes=60)

        assert result["symbol"] == "BTC/USD"
        assert result["period"] == 60
        assert result["volatility"] is not None
        assert result["volatility"] > 0
        assert result["atr"] is not None
        assert result["atr"] > 0

    def test_get_volatility_insufficient_data(self, client):
        """Test get_volatility with too few records."""
        self._mock_query(client, [[{"_time": "t0", "close": 100}]])
        result = client.get_volatility("BTC/USD")
        assert result["volatility"] is None
        assert result["atr"] is None

    def test_get_market_summary(self, client):
        """Test get_market_summary returns all expected fields."""
        records = []
        for i in range(100):
            records.append(
                {
                    "_time": f"t{i}",
                    "open": 50000 + i,
                    "high": 50100 + i,
                    "low": 49900 + i,
                    "close": 50000 + i * 10,
                    "volume": 1.0 + i * 0.1,
                }
            )
        self._mock_query(client, [records])

        result = client.get_market_summary("BTC/USD")

        assert result["symbol"] == "BTC/USD"
        assert result["price"] is not None
        assert result["high_24h"] is not None
        assert result["low_24h"] is not None
        assert result["volume_24h"] is not None
        assert result["vwap"] is not None
        assert result["change_24h"] is not None
        assert result["volatility"] is not None

    def test_get_market_summary_no_data(self, client):
        """Test get_market_summary with no data."""
        self._mock_query(client, [[]])
        result = client.get_market_summary("UNKNOWN/USD")
        assert result["price"] is None
        assert result["vwap"] is None

    def test_close(self, client):
        """Test close calls client.close()."""
        client.close()
        client.client.close.assert_called_once()
