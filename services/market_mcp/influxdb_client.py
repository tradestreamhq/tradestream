"""
InfluxDB client for the market MCP server.
Queries candle data from the InfluxDB candles measurement.
"""

from absl import logging
from influxdb_client import InfluxDBClient


class InfluxDBMarketClient:
    def __init__(self, url: str, token: str, org: str, bucket: str):
        self.url = url
        self.token = token
        self.org = org
        self.bucket = bucket
        self.client = InfluxDBClient(url=url, token=token, org=org)

    def query(self, flux_query: str) -> list[dict]:
        """Execute a Flux query and return results as list of dicts."""
        query_api = self.client.query_api()
        tables = query_api.query(flux_query, org=self.org)
        results = []
        for table in tables:
            for record in table.records:
                results.append(record.values)
        return results

    def get_candles(
        self,
        symbol: str,
        timeframe: str = "1m",
        start: str | None = None,
        end: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        """Query candles from InfluxDB for a given symbol."""
        range_clause = f'|> range(start: {start}, stop: {end})' if start and end else (
            f'|> range(start: {start})' if start else '|> range(start: -24h)'
        )

        query = f'''
            from(bucket: "{self.bucket}")
                {range_clause}
                |> filter(fn: (r) => r._measurement == "candles")
                |> filter(fn: (r) => r.currency_pair == "{symbol}")
                |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
                |> sort(columns: ["_time"], desc: false)
                |> limit(n: {limit})
        '''

        records = self.query(query)
        candles = []
        for r in records:
            candles.append({
                "timestamp": r.get("_time", "").isoformat() if hasattr(r.get("_time", ""), "isoformat") else str(r.get("_time", "")),
                "open": r.get("open"),
                "high": r.get("high"),
                "low": r.get("low"),
                "close": r.get("close"),
                "volume": r.get("volume"),
            })
        return candles

    def get_latest_price(self, symbol: str) -> dict:
        """Get the most recent candle close price for a symbol."""
        query = f'''
            from(bucket: "{self.bucket}")
                |> range(start: -24h)
                |> filter(fn: (r) => r._measurement == "candles")
                |> filter(fn: (r) => r.currency_pair == "{symbol}")
                |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
                |> sort(columns: ["_time"], desc: true)
                |> limit(n: 1)
        '''
        records = self.query(query)
        if not records:
            return {"symbol": symbol, "price": None, "volume_24h": None, "change_24h": None, "timestamp": None}

        latest = records[0]
        timestamp = latest.get("_time", "")
        price = latest.get("close")

        # Get 24h ago price for change calculation
        volume_24h = self._get_volume_24h(symbol)
        change_24h = self._get_change_24h(symbol, price)

        return {
            "symbol": symbol,
            "price": price,
            "volume_24h": volume_24h,
            "change_24h": change_24h,
            "timestamp": timestamp.isoformat() if hasattr(timestamp, "isoformat") else str(timestamp),
        }

    def get_volatility(self, symbol: str, period_minutes: int = 60) -> dict:
        """Compute volatility (stddev of returns) and ATR from recent candles."""
        query = f'''
            from(bucket: "{self.bucket}")
                |> range(start: -{period_minutes}m)
                |> filter(fn: (r) => r._measurement == "candles")
                |> filter(fn: (r) => r.currency_pair == "{symbol}")
                |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
                |> sort(columns: ["_time"], desc: false)
        '''
        records = self.query(query)
        if len(records) < 2:
            return {"symbol": symbol, "volatility": None, "atr": None, "period": period_minutes}

        # Calculate returns and stddev
        closes = [r.get("close", 0) for r in records if r.get("close") is not None]
        returns = []
        for i in range(1, len(closes)):
            if closes[i - 1] != 0:
                returns.append((closes[i] - closes[i - 1]) / closes[i - 1])

        volatility = None
        if returns:
            mean_return = sum(returns) / len(returns)
            variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
            volatility = variance ** 0.5

        # Calculate ATR
        true_ranges = []
        for i in range(1, len(records)):
            high = records[i].get("high", 0) or 0
            low = records[i].get("low", 0) or 0
            prev_close = records[i - 1].get("close", 0) or 0
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            true_ranges.append(tr)

        atr = sum(true_ranges) / len(true_ranges) if true_ranges else None

        return {"symbol": symbol, "volatility": volatility, "atr": atr, "period": period_minutes}

    def get_market_summary(self, symbol: str) -> dict:
        """Aggregate market summary: price, changes, volume, volatility, high/low, vwap."""
        # Get current price from latest candle
        query_latest = f'''
            from(bucket: "{self.bucket}")
                |> range(start: -24h)
                |> filter(fn: (r) => r._measurement == "candles")
                |> filter(fn: (r) => r.currency_pair == "{symbol}")
                |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
                |> sort(columns: ["_time"], desc: false)
        '''
        records = self.query(query_latest)
        if not records:
            return {
                "symbol": symbol, "price": None, "change_1h": None,
                "change_24h": None, "volume_24h": None, "volatility": None,
                "high_24h": None, "low_24h": None, "vwap": None,
            }

        latest = records[-1]
        price = latest.get("close")

        # 24h high/low/volume
        highs = [r.get("high", 0) for r in records if r.get("high") is not None]
        lows = [r.get("low", 0) for r in records if r.get("low") is not None]
        volumes = [r.get("volume", 0) for r in records if r.get("volume") is not None]

        high_24h = max(highs) if highs else None
        low_24h = min(lows) if lows else None
        volume_24h = sum(volumes) if volumes else None

        # VWAP calculation
        vwap = None
        if records:
            total_pv = 0.0
            total_vol = 0.0
            for r in records:
                typical_price = ((r.get("high") or 0) + (r.get("low") or 0) + (r.get("close") or 0)) / 3
                vol = r.get("volume") or 0
                total_pv += typical_price * vol
                total_vol += vol
            if total_vol > 0:
                vwap = total_pv / total_vol

        # 1h change
        change_1h = None
        one_hour_candles = [r for r in records]
        if len(one_hour_candles) >= 60 and price is not None:
            price_1h_ago = one_hour_candles[-60].get("close")
            if price_1h_ago and price_1h_ago != 0:
                change_1h = ((price - price_1h_ago) / price_1h_ago) * 100

        # 24h change
        change_24h = None
        if len(records) > 1 and price is not None:
            first_close = records[0].get("close")
            if first_close and first_close != 0:
                change_24h = ((price - first_close) / first_close) * 100

        # Volatility from returns
        closes = [r.get("close", 0) for r in records if r.get("close") is not None]
        volatility = None
        if len(closes) >= 2:
            returns = []
            for i in range(1, len(closes)):
                if closes[i - 1] != 0:
                    returns.append((closes[i] - closes[i - 1]) / closes[i - 1])
            if returns:
                mean_return = sum(returns) / len(returns)
                variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
                volatility = variance ** 0.5

        return {
            "symbol": symbol,
            "price": price,
            "change_1h": change_1h,
            "change_24h": change_24h,
            "volume_24h": volume_24h,
            "volatility": volatility,
            "high_24h": high_24h,
            "low_24h": low_24h,
            "vwap": vwap,
        }

    def _get_volume_24h(self, symbol: str) -> float | None:
        """Get total volume over last 24h."""
        query = f'''
            from(bucket: "{self.bucket}")
                |> range(start: -24h)
                |> filter(fn: (r) => r._measurement == "candles")
                |> filter(fn: (r) => r.currency_pair == "{symbol}")
                |> filter(fn: (r) => r._field == "volume")
                |> sum()
        '''
        records = self.query(query)
        if records:
            return records[0].get("_value")
        return None

    def _get_change_24h(self, symbol: str, current_price: float | None) -> float | None:
        """Calculate 24h price change percentage."""
        if current_price is None:
            return None
        query = f'''
            from(bucket: "{self.bucket}")
                |> range(start: -24h)
                |> filter(fn: (r) => r._measurement == "candles")
                |> filter(fn: (r) => r.currency_pair == "{symbol}")
                |> filter(fn: (r) => r._field == "close")
                |> first()
        '''
        records = self.query(query)
        if records:
            old_price = records[0].get("_value")
            if old_price and old_price != 0:
                return ((current_price - old_price) / old_price) * 100
        return None

    def close(self):
        """Close the InfluxDB client."""
        if self.client:
            self.client.close()
