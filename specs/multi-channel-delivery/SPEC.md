# Multi-Channel Delivery Specification

## Goal

Deliver trading signals to users wherever they are—web, Telegram, Discord, Slack, and push notifications—with consistent formatting and configurable preferences.

## Channels Overview

| Channel | Use Case | Implementation | Priority |
|---------|----------|----------------|----------|
| **Web Dashboard** | Primary interface, full reasoning | React app | P0 |
| **Telegram Bot** | Mobile alerts, quick commands | python-telegram-bot | P1 |
| **Discord Webhook** | Community/team alerts | Discord webhook API | P1 |
| **Slack** | Enterprise team integration | Slack Bolt SDK | P2 |
| **Push (PWA)** | Mobile web notifications | Web Push API | P2 |
| **Email Digest** | Daily/weekly summaries | SendGrid | P3 |

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    DELIVERY SERVICE                         │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Signal Consumer (Redis: channel:dashboard-signals)  │   │
│  └─────────────────────────────────────────────────────┘   │
│                              │                              │
│         ┌────────────────────┼────────────────────┐        │
│         ▼                    ▼                    ▼        │
│  ┌────────────┐      ┌────────────┐      ┌────────────┐   │
│  │ Formatter  │      │ Rate       │      │ User Prefs │   │
│  │ (per-chan) │      │ Limiter    │      │ Filter     │   │
│  └────────────┘      └────────────┘      └────────────┘   │
│         │                    │                    │        │
│         └────────────────────┼────────────────────┘        │
│                              ▼                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Channel Dispatchers                                 │   │
│  │                                                     │   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐  │   │
│  │  │Telegram │ │ Discord │ │  Slack  │ │  Push   │  │   │
│  └──┴─────────┴─┴─────────┴─┴─────────┴─┴─────────┴──┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## Telegram Bot

### Features

| Command | Description | Example |
|---------|-------------|---------|
| `/start` | Welcome and setup | Registration flow |
| `/signals` | Latest signals | Last 5 signals |
| `/signals ETH` | Symbol filter | ETH signals only |
| `/signals --hot` | Hot opportunities | Score > 80 only |
| `/ask <question>` | Research mode | "/ask Why did RSI trigger?" |
| `/follow BTC ETH` | Set watchlist | Subscribe to symbols |
| `/unfollow SOL` | Remove from watchlist | Unsubscribe |
| `/settings` | Configure alerts | Preferences menu |
| `/help` | Command reference | All commands |

### Alert Format

```
🔥 HOT OPPORTUNITY (Score: 87)
🟢 BUY ETH/USD

📊 Confidence: 82%
📈 Expected Return: +3.2% ± 1.5%
🎯 Strategy Consensus: 4/5 bullish

Top Strategy: RSI_REVERSAL
├ Accuracy: 62% (847 signals)
└ Reason: Oversold recovery, MACD crossed bullish

[View Details](https://app.tradestream.io/signal/abc123)
```

### Implementation

```python
# services/telegram_bot/main.py

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes

class TelegramBot:
    def __init__(self, config):
        self.config = config
        self.app = Application.builder().token(config.bot_token).build()
        self._setup_handlers()

    def _setup_handlers(self):
        self.app.add_handler(CommandHandler("start", self.start))
        self.app.add_handler(CommandHandler("signals", self.signals))
        self.app.add_handler(CommandHandler("ask", self.ask))
        self.app.add_handler(CommandHandler("follow", self.follow))
        self.app.add_handler(CommandHandler("settings", self.settings))

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Welcome message and registration."""
        user_id = update.effective_user.id
        await self.user_service.register(user_id, "telegram")

        await update.message.reply_text(
            "👋 Welcome to TradeStream!\n\n"
            "I'll send you trading signals backed by millions of validated strategies.\n\n"
            "Commands:\n"
            "/signals - View latest signals\n"
            "/follow BTC ETH - Subscribe to symbols\n"
            "/settings - Configure alerts\n"
            "/help - All commands"
        )

    async def signals(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show recent signals with optional filters."""
        args = context.args
        filters = self._parse_signal_args(args)

        signals = await self.signal_service.get_recent(
            user_id=update.effective_user.id,
            **filters
        )

        for signal in signals[:5]:
            message = self.format_signal(signal)
            await update.message.reply_text(
                message,
                parse_mode="Markdown",
                disable_web_page_preview=True
            )

    def format_signal(self, signal: Signal) -> str:
        """Format signal for Telegram."""
        tier_emoji = {"HOT": "🔥", "GOOD": "⭐", "NEUTRAL": "⚪", "LOW": "🔹"}
        action_emoji = {"BUY": "🟢", "SELL": "🔴", "HOLD": "⚪"}

        return f"""
{tier_emoji[signal.opportunity_tier]} {signal.opportunity_tier} OPPORTUNITY (Score: {signal.opportunity_score})
{action_emoji[signal.action]} {signal.action} {signal.symbol}

📊 Confidence: {signal.confidence * 100:.0f}%
📈 Expected Return: +{signal.expected_return * 100:.1f}%
🎯 Strategy Consensus: {signal.strategies_bullish}/{signal.strategies_analyzed} bullish

Top Strategy: {signal.top_strategy.name}
├ Accuracy: {signal.top_strategy.accuracy * 100:.0f}%
└ Reason: {signal.reasoning[:100]}...

[View Details](https://app.tradestream.io/signal/{signal.signal_id})
"""

    async def send_alert(self, user_id: int, signal: Signal):
        """Send alert to user if matches preferences."""
        prefs = await self.user_service.get_preferences(user_id)

        if not self._should_send(signal, prefs):
            return

        if self._is_rate_limited(user_id, signal.symbol):
            return

        message = self.format_signal(signal)
        await self.app.bot.send_message(
            chat_id=user_id,
            text=message,
            parse_mode="Markdown"
        )
```

---

## Discord Webhook

### Alert Format

```
**🔥 HOT OPPORTUNITY** (Score: 87)

**🟢 BUY ETH/USD**

> **Confidence:** 82%
> **Expected Return:** +3.2% ± 1.5%
> **Strategy Consensus:** 4/5 bullish
>
> **Top Strategy:** RSI_REVERSAL
> *Accuracy: 62% | Reason: Oversold recovery*

[View in Dashboard →](https://app.tradestream.io/signal/abc123)

---
*Powered by TradeStream • 40M+ validated strategies*
```

### Implementation

```python
# services/discord_webhook/main.py

import aiohttp

class DiscordWebhook:
    def __init__(self, config):
        self.config = config
        self.webhook_url = config.webhook_url

    async def send_signal(self, signal: Signal):
        """Send signal to Discord webhook."""
        embed = self._create_embed(signal)

        async with aiohttp.ClientSession() as session:
            await session.post(
                self.webhook_url,
                json={"embeds": [embed]}
            )

    def _create_embed(self, signal: Signal) -> dict:
        """Create Discord embed for signal."""
        color = {
            "BUY": 0x00ff00,   # Green
            "SELL": 0xff0000,  # Red
            "HOLD": 0x808080   # Gray
        }[signal.action]

        tier_emoji = {"HOT": "🔥", "GOOD": "⭐", "NEUTRAL": "⚪", "LOW": "🔹"}
        action_emoji = {"BUY": "🟢", "SELL": "🔴", "HOLD": "⚪"}

        return {
            "title": f"{tier_emoji[signal.opportunity_tier]} {signal.opportunity_tier} OPPORTUNITY (Score: {signal.opportunity_score})",
            "description": f"{action_emoji[signal.action]} **{signal.action} {signal.symbol}**",
            "color": color,
            "fields": [
                {
                    "name": "📊 Confidence",
                    "value": f"{signal.confidence * 100:.0f}%",
                    "inline": True
                },
                {
                    "name": "📈 Expected Return",
                    "value": f"+{signal.expected_return * 100:.1f}%",
                    "inline": True
                },
                {
                    "name": "🎯 Strategy Consensus",
                    "value": f"{signal.strategies_bullish}/{signal.strategies_analyzed} bullish",
                    "inline": True
                },
                {
                    "name": "Top Strategy",
                    "value": f"**{signal.top_strategy.name}**\nAccuracy: {signal.top_strategy.accuracy * 100:.0f}%",
                    "inline": False
                }
            ],
            "footer": {
                "text": "Powered by TradeStream • 40M+ validated strategies"
            },
            "url": f"https://app.tradestream.io/signal/{signal.signal_id}"
        }
```

---

## Slack Integration

### Features

- Slash commands: `/tradestream signals`, `/tradestream ask`
- Interactive buttons for actions
- Thread replies for follow-up
- Channel configuration per workspace

### Alert Format

```
:fire: *HOT OPPORTUNITY* (Score: 87)

:large_green_circle: *BUY ETH/USD*

• *Confidence:* 82%
• *Expected Return:* +3.2% ± 1.5%
• *Strategy Consensus:* 4/5 bullish

*Top Strategy:* RSI_REVERSAL
_Accuracy: 62% | Reason: Oversold recovery_

<https://app.tradestream.io/signal/abc123|View in Dashboard →>
```

### Implementation

```python
# services/slack_bot/main.py

from slack_bolt.async_app import AsyncApp

class SlackBot:
    def __init__(self, config):
        self.app = AsyncApp(
            token=config.bot_token,
            signing_secret=config.signing_secret
        )
        self._setup_handlers()

    def _setup_handlers(self):
        self.app.command("/tradestream")(self.handle_command)

    async def handle_command(self, ack, command, respond):
        await ack()

        args = command["text"].split()
        if not args:
            await respond("Usage: /tradestream [signals|ask|follow|settings]")
            return

        action = args[0]
        if action == "signals":
            await self._show_signals(respond, args[1:])
        elif action == "ask":
            await self._ask_agent(respond, " ".join(args[1:]))

    async def send_alert(self, channel_id: str, signal: Signal):
        """Send signal alert to Slack channel."""
        blocks = self._create_blocks(signal)
        await self.app.client.chat_postMessage(
            channel=channel_id,
            blocks=blocks,
            text=f"{signal.action} {signal.symbol} - Score: {signal.opportunity_score}"
        )
```

---

## Push Notifications (PWA)

### Implementation

```typescript
// ui/agent-dashboard/src/lib/push-notifications.ts

export async function requestNotificationPermission(): Promise<boolean> {
  if (!('Notification' in window)) {
    return false;
  }

  const permission = await Notification.requestPermission();
  return permission === 'granted';
}

export async function subscribeToPush(): Promise<PushSubscription | null> {
  const registration = await navigator.serviceWorker.ready;

  const subscription = await registration.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: import.meta.env.VITE_VAPID_PUBLIC_KEY
  });

  // Send subscription to backend
  await fetch('/api/push/subscribe', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(subscription)
  });

  return subscription;
}

// Service Worker
self.addEventListener('push', (event) => {
  const data = event.data?.json();

  const options = {
    body: `${data.action} ${data.symbol} - Score: ${data.opportunity_score}`,
    icon: '/icon-192.png',
    badge: '/badge-72.png',
    tag: data.signal_id,
    data: { url: `/signal/${data.signal_id}` },
    actions: [
      { action: 'view', title: 'View Details' },
      { action: 'dismiss', title: 'Dismiss' }
    ]
  };

  event.waitUntil(
    self.registration.showNotification(
      `${data.opportunity_tier} Opportunity`,
      options
    )
  );
});
```

---

## Rate Limiting

### Per-User Limits

| Channel | Limit | Window |
|---------|-------|--------|
| Telegram | 1 per symbol | 5 minutes |
| Discord | 1 per symbol | 5 minutes |
| Slack | 1 per symbol | 5 minutes |
| Push | 5 total | 1 hour |

### Implementation

```python
class RateLimiter:
    def __init__(self, redis: Redis):
        self.redis = redis

    async def is_rate_limited(
        self,
        user_id: str,
        channel: str,
        symbol: str,
        window_seconds: int = 300
    ) -> bool:
        key = f"ratelimit:{channel}:{user_id}:{symbol}"
        exists = await self.redis.exists(key)

        if exists:
            return True

        await self.redis.setex(key, window_seconds, "1")
        return False
```

---

## User Preferences

### Schema

```sql
CREATE TABLE user_channel_preferences (
    user_id UUID NOT NULL,
    channel VARCHAR(50) NOT NULL,  -- telegram, discord, slack, push
    channel_id VARCHAR(255),       -- telegram chat_id, slack channel, etc.
    enabled BOOLEAN DEFAULT TRUE,
    min_opportunity_score INTEGER DEFAULT 60,
    symbols TEXT[],                -- NULL = all symbols
    actions TEXT[],                -- NULL = all actions
    quiet_hours_start TIME,
    quiet_hours_end TIME,
    timezone VARCHAR(50) DEFAULT 'UTC',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (user_id, channel)
);
```

### Preferences API

```
GET  /api/user/channels              # List configured channels
POST /api/user/channels/telegram     # Enable Telegram
PUT  /api/user/channels/telegram     # Update preferences
DELETE /api/user/channels/telegram   # Disable channel
```

---

## Configuration

```yaml
delivery:
  telegram:
    bot_token: ${TELEGRAM_BOT_TOKEN}
    rate_limit:
      per_symbol_seconds: 300

  discord:
    # Configured per-server via OAuth
    rate_limit:
      per_symbol_seconds: 300

  slack:
    bot_token: ${SLACK_BOT_TOKEN}
    signing_secret: ${SLACK_SIGNING_SECRET}
    rate_limit:
      per_symbol_seconds: 300

  push:
    vapid_private_key: ${VAPID_PRIVATE_KEY}
    vapid_public_key: ${VAPID_PUBLIC_KEY}
    rate_limit:
      per_hour: 5
```

## Constraints

- Users must opt-in to each channel
- Rate limits prevent spam
- Configurable minimum opportunity score for alerts
- Quiet hours support per user
- Graceful degradation if channel unavailable

## Acceptance Criteria

- [ ] Telegram bot responds to /signals command
- [ ] Discord webhook posts formatted alerts
- [ ] Users can configure alert preferences
- [ ] Rate limiting prevents spam (1 per symbol per 5 min)
- [ ] Quiet hours respected
- [ ] Minimum opportunity score filter works
- [ ] All channels show consistent signal information
- [ ] Failed delivery logged but doesn't block others

## File Structure

```
services/
├── delivery/
│   ├── __init__.py
│   ├── main.py              # Delivery orchestrator
│   ├── rate_limiter.py      # Rate limiting
│   ├── formatters/
│   │   ├── telegram.py
│   │   ├── discord.py
│   │   └── slack.py
│   └── preferences.py       # User preferences
├── telegram_bot/
│   ├── main.py
│   ├── handlers.py
│   └── Dockerfile
├── discord_webhook/
│   ├── main.py
│   └── Dockerfile
└── slack_bot/
    ├── main.py
    ├── handlers.py
    └── Dockerfile
```
