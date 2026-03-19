# Telegram Bot Integration Guide

## Overview

Receive trading signals and opportunity alerts directly in Telegram via
@TradeStreamBot. Supports compact and detailed signal formats.

## Setup

### Step 1: Generate a connection code

```bash
curl -X POST https://api.tradestream.io/api/v1/integrations/telegram/connect \
  -H "X-API-Key: YOUR_KEY"
```

Response:

```json
{
  "verification_code": "TS-482910",
  "bot_username": "@TradeStreamBot",
  "instructions": "Send this code to @TradeStreamBot on Telegram within 10 minutes",
  "expires_in_minutes": 10
}
```

### Step 2: Link your account

1. Open Telegram and search for **@TradeStreamBot**
2. Start a chat and send `/start`
3. Send your verification code: `TS-482910`
4. The bot confirms the link

### Step 3: Configure signal format

```bash
curl -X PUT https://api.tradestream.io/api/v1/integrations/telegram \
  -H "X-API-Key: YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "signal_format": "detailed",
    "enabled": true
  }'
```

Signal format options:

| Format     | Description                                         |
|------------|-----------------------------------------------------|
| `compact`  | One-line: `BUY BTC/USD @ 67,500 (strength: 0.85)`  |
| `detailed` | Full card with entry, SL, TP, indicators, timeframe |
| `custom`   | User-defined template (coming soon)                 |

### Step 4: Send a test message

```bash
curl -X POST https://api.tradestream.io/api/v1/integrations/telegram/test \
  -H "X-API-Key: YOUR_KEY"
```

## Bot Commands

| Command         | Description                          |
|-----------------|--------------------------------------|
| `/start`        | Start the bot and see welcome info   |
| `/status`       | View active subscriptions            |
| `/signals`      | List recent signals                  |
| `/portfolio`    | Quick portfolio summary              |
| `/opportunities`| Top active opportunities             |
| `/mute 1h`      | Mute notifications for 1 hour        |
| `/unmute`       | Resume notifications                 |
| `/help`         | List all commands                    |

## Disconnect

```bash
curl -X POST https://api.tradestream.io/api/v1/integrations/telegram/disconnect \
  -H "X-API-Key: YOUR_KEY"
```

Or send `/disconnect` to @TradeStreamBot.
