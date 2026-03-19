# Discord Integration Guide

## Overview

Deliver trading signals to a Discord channel using webhook embeds.
Supports rich embeds with color-coded buy/sell signals and optional role mentions.

## Setup

### Step 1: Create a Discord webhook

1. Go to your Discord server settings
2. Navigate to **Integrations > Webhooks**
3. Click **New Webhook**
4. Choose the target channel (e.g., #trading-signals)
5. Copy the webhook URL

### Step 2: Configure in TradeStream

```bash
curl -X PUT https://api.tradestream.io/api/v1/integrations/discord \
  -H "X-API-Key: YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "webhook_url": "https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_TOKEN",
    "embed_format": true,
    "mention_role_id": "123456789",
    "enabled": true
  }'
```

| Option            | Description                                     |
| ----------------- | ----------------------------------------------- |
| `webhook_url`     | Discord webhook URL from server settings        |
| `embed_format`    | `true` for rich embeds, `false` for plain text  |
| `mention_role_id` | Discord role ID to @mention on S/A-tier signals |
| `enabled`         | Toggle delivery on/off                          |

### Step 3: Test the integration

```bash
curl -X POST https://api.tradestream.io/api/v1/integrations/discord/test \
  -H "X-API-Key: YOUR_KEY"
```

This sends a sample signal embed to your Discord channel.

## Signal Embed Format

When `embed_format: true`, signals appear as rich Discord embeds:

- **Green** embed border for BUY signals
- **Red** embed border for SELL signals
- Fields: Instrument, Direction, Strength, Entry/SL/TP, Timeframe
- Footer: Strategy name and timestamp

## Role Mentions

Set `mention_role_id` to a Discord role ID to @mention that role when
high-tier (S or A) signals are generated. To find a role ID:

1. Enable Developer Mode in Discord settings
2. Right-click the role > Copy ID
