"""Data models for TradingView webhook integration."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class TradingViewAction(str, Enum):
    """TradingView alert actions mapped to TradeStream signal types."""

    BUY = "buy"
    SELL = "sell"
    CLOSE = "close"
    LONG = "long"
    SHORT = "short"
    EXIT_LONG = "exit_long"
    EXIT_SHORT = "exit_short"


# Map TradingView actions to internal signal types
ACTION_TO_SIGNAL_TYPE = {
    TradingViewAction.BUY: "BUY",
    TradingViewAction.LONG: "BUY",
    TradingViewAction.SELL: "SELL",
    TradingViewAction.SHORT: "SELL",
    TradingViewAction.CLOSE: "SELL",
    TradingViewAction.EXIT_LONG: "SELL",
    TradingViewAction.EXIT_SHORT: "BUY",
}


class TradingViewWebhookPayload(BaseModel):
    """Incoming TradingView alert webhook payload.

    TradingView alerts send JSON payloads configured in the alert message.
    This model covers the common fields used in Pine Script strategy alerts.
    """

    ticker: str = Field(..., description="Trading pair/symbol (e.g., BTCUSD, AAPL)")
    action: str = Field(
        ...,
        description="Trade action: buy, sell, long, short, close, exit_long, exit_short",
    )
    price: Optional[float] = Field(None, description="Price at signal time")
    stop_loss: Optional[float] = Field(
        None, alias="stoploss", description="Stop loss price"
    )
    take_profit: Optional[float] = Field(
        None, alias="takeprofit", description="Take profit price"
    )
    quantity: Optional[float] = Field(None, description="Position size / quantity")
    strategy: Optional[str] = Field(None, description="Strategy name from TradingView")
    message: Optional[str] = Field(None, description="Custom alert message")
    time: Optional[str] = Field(None, description="Alert timestamp from TradingView")
    interval: Optional[str] = Field(
        None, description="Chart timeframe (e.g., 1H, 4H, 1D)"
    )
    exchange: Optional[str] = Field(
        None, description="Exchange name (e.g., BINANCE, NYSE)"
    )

    model_config = {"populate_by_name": True}


class TradingViewConnection(BaseModel):
    """A user's TradingView integration connection."""

    id: Optional[str] = None
    name: str = Field(..., description="Connection name (e.g., 'My BTC Strategy')")
    webhook_token: Optional[str] = Field(
        None, description="Secret token for webhook URL authentication"
    )
    strategy_name: Optional[str] = Field(
        None, description="Map incoming alerts to this TradeStream strategy"
    )
    instrument: Optional[str] = Field(
        None, description="Override instrument mapping (e.g., BTC/USD)"
    )
    active: bool = Field(True, description="Whether this connection is active")
    alert_mapping: Optional[Dict[str, str]] = Field(
        None, description="Custom action-to-signal mapping overrides"
    )


class PineScriptConfig(BaseModel):
    """Configuration for generating Pine Script indicator code."""

    strategy_name: str = Field(..., description="Strategy name for the Pine Script")
    webhook_url: str = Field(..., description="Full webhook URL to send alerts to")
    ticker: Optional[str] = Field(
        None, description="Symbol override (defaults to chart symbol)"
    )
    include_stop_loss: bool = Field(
        True, description="Include stop_loss in alert payload"
    )
    include_take_profit: bool = Field(
        True, description="Include take_profit in alert payload"
    )
    include_quantity: bool = Field(
        True, description="Include quantity in alert payload"
    )


def normalize_ticker(ticker: str) -> str:
    """Normalize a TradingView ticker to TradeStream instrument format.

    TradingView: BTCUSD, BINANCE:BTCUSDT, AAPL
    TradeStream: BTC/USD, BTC/USDT, AAPL/USD
    """
    # Strip exchange prefix
    if ":" in ticker:
        ticker = ticker.split(":", 1)[1]

    ticker = ticker.upper()

    # Common quote currencies to split on
    for quote in ("USDT", "USD", "EUR", "GBP", "BTC", "ETH", "BUSD"):
        if ticker.endswith(quote) and len(ticker) > len(quote):
            base = ticker[: -len(quote)]
            return f"{base}/{quote}"

    # No known quote currency — return as-is (e.g., single stock)
    return ticker


def tradingview_payload_to_signal(
    payload: TradingViewWebhookPayload,
    connection: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Convert a TradingView webhook payload to an internal signal dict."""
    action_lower = payload.action.lower().strip()

    # Check custom mapping from connection config
    custom_mapping = (connection or {}).get("alert_mapping") or {}
    signal_type = custom_mapping.get(action_lower)

    if not signal_type:
        try:
            tv_action = TradingViewAction(action_lower)
            signal_type = ACTION_TO_SIGNAL_TYPE[tv_action]
        except ValueError:
            signal_type = action_lower.upper()

    # Determine instrument
    instrument = (connection or {}).get("instrument") or normalize_ticker(
        payload.ticker
    )

    # Determine strategy name
    strategy_name = (
        (connection or {}).get("strategy_name")
        or payload.strategy
        or "tradingview_alert"
    )

    signal = {
        "instrument": instrument,
        "signal_type": signal_type,
        "strategy_name": strategy_name,
        "price": payload.price,
        "stop_loss": payload.stop_loss,
        "take_profit": payload.take_profit,
        "position_size": payload.quantity,
        "strength": 1.0,  # TradingView alerts are binary, full confidence
        "source": "tradingview",
        "metadata": {
            "tradingview_ticker": payload.ticker,
            "tradingview_action": payload.action,
            "tradingview_message": payload.message,
            "tradingview_interval": payload.interval,
            "tradingview_exchange": payload.exchange,
            "tradingview_time": payload.time,
        },
    }

    return signal
