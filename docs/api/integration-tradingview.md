# TradingView Integration Guide

## Overview

Connect TradingView alerts to TradeStream to automatically create trading
signals from your Pine Script strategies and manual chart analysis.

## Setup

### Step 1: Get your webhook URL

```bash
curl https://api.tradestream.io/api/v1/integrations/tradingview \
  -H "X-API-Key: YOUR_KEY"
```

Response:

```json
{
  "webhook_url": "https://api.tradestream.io/api/v1/integrations/tradingview/webhook/YOUR_TOKEN",
  "webhook_secret": "whsec_...",
  "instrument_mapping": {},
  "auto_subscribe": false,
  "enabled": true
}
```

### Step 2: Configure instrument mapping

Map TradingView ticker names to TradeStream instrument symbols:

```bash
curl -X PUT https://api.tradestream.io/api/v1/integrations/tradingview \
  -H "X-API-Key: YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "instrument_mapping": {
      "BTCUSD": "BTC/USD",
      "ETHUSD": "ETH/USD",
      "SOLUSD": "SOL/USD",
      "BINANCE:BTCUSDT": "BTC/USD"
    },
    "auto_subscribe": true,
    "enabled": true
  }'
```

### Step 3: Create a TradingView alert

1. Open your chart on TradingView
2. Click "Alert" (clock icon) or press Alt+A
3. Set your condition (indicator, price, etc.)
4. In the **Notifications** tab:
   - Check "Webhook URL"
   - Paste your TradeStream webhook URL
5. In the **Message** field, use this JSON template:

```json
{
  "ticker": "{{ticker}}",
  "exchange": "{{exchange}}",
  "action": "buy",
  "price": {{close}},
  "timeframe": "{{interval}}",
  "strategy_name": "My RSI Strategy",
  "comment": "RSI crossed below 30"
}
```

### Step 4: Get a Pine Script template (optional)

```bash
curl "https://api.tradestream.io/api/v1/integrations/tradingview/pine-template?strategy_type=rsi" \
  -H "X-API-Key: YOUR_KEY"
```

This returns a Pine Script pre-configured with the correct alert JSON format.

## Alert JSON Format

| Field          | Required | Description                           |
|----------------|----------|---------------------------------------|
| `ticker`       | Yes      | TradingView ticker symbol             |
| `exchange`     | No       | Exchange name                         |
| `action`       | Yes      | `buy`, `sell`, or `close`             |
| `price`        | No       | Alert trigger price                   |
| `volume`       | No       | Current volume                        |
| `timeframe`    | No       | Chart timeframe (e.g., `240` for 4h)  |
| `strategy_name`| No       | Strategy identifier                   |
| `comment`      | No       | Free-text context from Pine Script    |

## TradingView Variables

Use these in your alert message for dynamic values:

| Variable        | Value                    |
|-----------------|--------------------------|
| `{{ticker}}`    | Symbol (e.g., BTCUSD)    |
| `{{exchange}}`  | Exchange name             |
| `{{close}}`     | Close price at trigger    |
| `{{open}}`      | Open price                |
| `{{high}}`      | High price                |
| `{{low}}`       | Low price                 |
| `{{volume}}`    | Volume                    |
| `{{interval}}`  | Timeframe                 |
| `{{time}}`      | Alert time (Unix)         |

## Troubleshooting

- **Alert not received**: Verify the webhook URL is correct and `enabled: true`
- **Instrument not mapped**: Check your instrument_mapping configuration
- **TradingView free plan**: Free accounts are limited to 1 active alert
