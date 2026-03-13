"""
Indicators REST API — RMM Level 2.

Provides an endpoint to compute technical indicators for a trading pair,
backed by candle data from InfluxDB.
"""

import logging
from dataclasses import asdict
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, FastAPI, Query
from pydantic import BaseModel, Field

from services.indicators.library import (
    ATR,
    EMA,
    MACD,
    RSI,
    SMA,
    VWAP,
    BollingerBands,
    BollingerBandsResult,
    Candle,
    MACDResult,
    StochasticOscillator,
    StochasticResult,
    compute_indicators,
)
from services.rest_api_shared.health import create_health_router
from services.rest_api_shared.responses import (
    not_found,
    server_error,
    success_response,
    validation_error,
)
from services.shared.auth import fastapi_auth_middleware

logger = logging.getLogger(__name__)

# Supported indicator names and their default parameters
INDICATOR_DEFAULTS: Dict[str, Dict[str, Any]] = {
    "sma": {"period": 20},
    "ema": {"period": 12},
    "rsi": {"period": 14},
    "macd": {"fast_period": 12, "slow_period": 26, "signal_period": 9},
    "bollinger_bands": {"period": 20, "num_std": 2.0},
    "atr": {"period": 14},
    "vwap": {},
    "stochastic": {"k_period": 14, "d_period": 3},
}


def _serialize_results(name: str, values: list) -> list:
    """Convert indicator results to JSON-serializable format."""
    out = []
    for v in values:
        if v is None:
            out.append(None)
        elif isinstance(v, (MACDResult, BollingerBandsResult, StochasticResult)):
            out.append(asdict(v))
        else:
            out.append(v)
    return out


def create_app(influxdb_client) -> FastAPI:
    """Create the Indicators API FastAPI application."""
    app = FastAPI(
        title="Indicators API",
        version="1.0.0",
        docs_url="/docs",
        root_path="/api/v1/indicators",
    )
    fastapi_auth_middleware(app)

    async def check_deps():
        return {"influxdb": "ok"}

    app.include_router(create_health_router("indicators-api", check_deps))

    router = APIRouter(tags=["Indicators"])

    @router.get("/{pair}")
    async def get_indicators(
        pair: str,
        indicators: str = Query(
            "sma,ema,rsi",
            description="Comma-separated list of indicators to compute",
        ),
        interval: str = Query(
            "1h",
            description="Candle interval",
            regex="^(1m|5m|15m|1h|4h|1d)$",
        ),
        limit: int = Query(
            100, ge=1, le=1000, description="Number of candles to fetch"
        ),
        sma_period: int = Query(20, ge=1, description="SMA period"),
        ema_period: int = Query(12, ge=1, description="EMA period"),
        rsi_period: int = Query(14, ge=1, description="RSI period"),
        macd_fast: int = Query(12, ge=1, description="MACD fast period"),
        macd_slow: int = Query(26, ge=1, description="MACD slow period"),
        macd_signal: int = Query(9, ge=1, description="MACD signal period"),
        bb_period: int = Query(20, ge=1, description="Bollinger Bands period"),
        bb_std: float = Query(2.0, gt=0, description="Bollinger Bands std devs"),
        atr_period: int = Query(14, ge=1, description="ATR period"),
        stoch_k: int = Query(14, ge=1, description="Stochastic %K period"),
        stoch_d: int = Query(3, ge=1, description="Stochastic %D period"),
    ):
        """Compute technical indicators for a trading pair."""
        requested = [i.strip().lower() for i in indicators.split(",") if i.strip()]
        invalid = [i for i in requested if i not in INDICATOR_DEFAULTS]
        if invalid:
            return validation_error(
                f"Unknown indicators: {', '.join(invalid)}",
                details=[
                    {"available": ", ".join(sorted(INDICATOR_DEFAULTS.keys()))}
                ],
            )

        raw_candles = influxdb_client.get_candles(
            symbol=pair, timeframe=interval, start=None, limit=limit
        )
        if not raw_candles:
            return not_found("Candle data", pair)

        candles = [
            Candle(
                timestamp=c.get("time", ""),
                open=c["open"],
                high=c["high"],
                low=c["low"],
                close=c["close"],
                volume=c.get("volume", 0.0),
            )
            for c in raw_candles
        ]

        config: Dict[str, Dict[str, Any]] = {}
        for name in requested:
            if name == "sma":
                config["sma"] = {"period": sma_period}
            elif name == "ema":
                config["ema"] = {"period": ema_period}
            elif name == "rsi":
                config["rsi"] = {"period": rsi_period}
            elif name == "macd":
                config["macd"] = {
                    "fast_period": macd_fast,
                    "slow_period": macd_slow,
                    "signal_period": macd_signal,
                }
            elif name == "bollinger_bands":
                config["bollinger_bands"] = {
                    "period": bb_period,
                    "num_std": bb_std,
                }
            elif name == "atr":
                config["atr"] = {"period": atr_period}
            elif name == "vwap":
                config["vwap"] = {}
            elif name == "stochastic":
                config["stochastic"] = {"k_period": stoch_k, "d_period": stoch_d}

        results = compute_indicators(candles, config)

        serialized = {
            name: _serialize_results(name, vals)
            for name, vals in results.items()
        }

        return success_response(
            {
                "pair": pair,
                "interval": interval,
                "candle_count": len(candles),
                "indicators": serialized,
            },
            "indicator_result",
            resource_id=pair,
        )

    app.include_router(router)
    return app
