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
┌─────────────────────────────────────────────────────────────────────────┐
│                           DELIVERY SERVICE                               │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │ Signal Consumer (Kafka: agent-dashboard-signals)              │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                    │                                     │
│                                    ▼                                     │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │ Cross-Channel Deduplication (per signal_id + user_id)           │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                    │                                     │
│         ┌──────────────────────────┼──────────────────────────┐         │
│         ▼                          ▼                          ▼         │
│  ┌────────────┐            ┌────────────┐            ┌────────────┐    │
│  │ Template   │            │ Rate       │            │ User Prefs │    │
│  │ Engine     │            │ Limiter    │            │ Filter     │    │
│  └────────────┘            └────────────┘            └────────────┘    │
│         │                          │                          │         │
│         └──────────────────────────┼──────────────────────────┘         │
│                                    ▼                                     │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │ Channel Dispatchers (with retry + exponential backoff)          │    │
│  │                                                                  │    │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐   │    │
│  │  │Telegram │ │ Discord │ │  Slack  │ │  Push   │ │ Email   │   │    │
│  └──┴─────────┴─┴─────────┴─┴─────────┴─┴─────────┴─┴─────────┴───┘    │
│                                    │                                     │
│                                    ▼                                     │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │ Delivery Tracker (receipts, confirmations, metrics)             │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                    │                                     │
│                              ┌─────┴─────┐                              │
│                              ▼           ▼                              │
│                     ┌─────────────┐ ┌─────────────┐                     │
│                     │ Success Log │ │ Dead Letter │                     │
│                     │             │ │ Queue (DLQ) │                     │
│                     └─────────────┘ └─────────────┘                     │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Cross-Channel Deduplication

Prevents the same signal from being sent multiple times to a user across different channels when a single notification would suffice.

### Strategy

Each signal delivery is tracked by a composite key of `signal_id + user_id`. When a signal is delivered to any channel, subsequent attempts to deliver the same signal to the same user on other channels are deduplicated based on user preference.

### User Preference Options

| Option | Behavior |
|--------|----------|
| `primary_only` | Send to primary channel only (default) |
| `all_enabled` | Send to all enabled channels (opt-in for power users) |
| `fallback_chain` | Try primary, fallback to next if failed |

### Implementation

```python
class CrossChannelDeduplicator:
    def __init__(self, kafka: Kafka):
        self.kafka = kafka
        self.ttl_seconds = 3600  # 1 hour dedup window

    async def should_deliver(
        self,
        signal_id: str,
        user_id: str,
        channel: str,
        preference: str = "primary_only"
    ) -> bool:
        """Check if signal should be delivered to this channel."""
        key = f"dedup:{user_id}:{signal_id}"

        if preference == "all_enabled":
            # Allow delivery to all channels
            return True

        delivered_channels = await self.kafka.smembers(key)

        if preference == "primary_only":
            # Block if already delivered to any channel
            return len(delivered_channels) == 0

        if preference == "fallback_chain":
            # Allow only if previous channels failed
            return all(
                await self._channel_failed(signal_id, user_id, ch)
                for ch in delivered_channels
            )

        return True

    async def mark_delivered(
        self,
        signal_id: str,
        user_id: str,
        channel: str
    ) -> None:
        """Record successful delivery."""
        key = f"dedup:{user_id}:{signal_id}"
        await self.kafka.sadd(key, channel)
        await self.kafka.expire(key, self.ttl_seconds)
```

---

## Message Templating System

Provides consistent formatting across all channels while respecting platform-specific constraints.

### Template Structure

```python
@dataclass
class SignalTemplate:
    """Canonical signal data for templating."""
    signal_id: str
    symbol: str
    action: str                    # BUY, SELL, HOLD
    opportunity_tier: str          # HOT, GOOD, NEUTRAL, LOW
    opportunity_score: int         # 0-100
    confidence: float              # 0.0-1.0
    expected_return: float         # percentage
    expected_return_std: float     # standard deviation
    strategies_bullish: int
    strategies_analyzed: int
    top_strategy_name: str
    top_strategy_accuracy: float
    reasoning: str
    dashboard_url: str
```

### Channel Adapters

```python
class TemplateEngine:
    """Renders signal templates for each channel."""

    TIER_EMOJI = {"HOT": "fire", "GOOD": "star", "NEUTRAL": "white_circle", "LOW": "small_blue_diamond"}
    ACTION_EMOJI = {"BUY": "green_circle", "SELL": "red_circle", "HOLD": "white_circle"}

    def render(self, template: SignalTemplate, channel: str) -> str:
        """Render template for specific channel."""
        renderer = getattr(self, f"_render_{channel}", self._render_default)
        return renderer(template)

    def _render_telegram(self, t: SignalTemplate) -> str:
        return f"""
{self._emoji(t.opportunity_tier)} {t.opportunity_tier} OPPORTUNITY (Score: {t.opportunity_score})
{self._emoji(t.action)} {t.action} {t.symbol}

📊 Confidence: {t.confidence * 100:.0f}%
📈 Expected Return: +{t.expected_return * 100:.1f}% ± {t.expected_return_std * 100:.1f}%
🎯 Strategy Consensus: {t.strategies_bullish}/{t.strategies_analyzed} bullish

Top Strategy: {t.top_strategy_name}
├ Accuracy: {t.top_strategy_accuracy * 100:.0f}%
└ Reason: {t.reasoning[:100]}...

[View Details]({t.dashboard_url})
"""

    def _render_discord(self, t: SignalTemplate) -> dict:
        """Returns Discord embed structure."""
        # ... (existing Discord implementation)

    def _render_slack(self, t: SignalTemplate) -> dict:
        """Returns Slack blocks structure."""
        # ... (existing Slack implementation)

    def _render_push(self, t: SignalTemplate) -> dict:
        """Returns compact push notification payload."""
        return {
            "title": f"{t.opportunity_tier} Opportunity",
            "body": f"{t.action} {t.symbol} - Score: {t.opportunity_score}",
            "tag": t.signal_id,
            "data": {"url": t.dashboard_url}
        }

    def _emoji(self, key: str) -> str:
        """Platform-agnostic emoji lookup."""
        mapping = {**self.TIER_EMOJI, **self.ACTION_EMOJI}
        return mapping.get(key, "")
```

---

## Retry Strategy and Dead Letter Queue

### Retry with Exponential Backoff

Failed deliveries are retried with exponential backoff before moving to the dead letter queue.

| Attempt | Delay | Cumulative Time |
|---------|-------|-----------------|
| 1 | Immediate | 0s |
| 2 | 1s | 1s |
| 3 | 2s | 3s |
| 4 | 4s | 7s |
| 5 | 8s | 15s |
| 6 (final) | 16s | 31s |

### Retry Implementation

```python
import asyncio
from dataclasses import dataclass
from enum import Enum
from typing import Optional

class DeliveryStatus(Enum):
    PENDING = "pending"
    DELIVERED = "delivered"
    RETRYING = "retrying"
    FAILED = "failed"         # Exhausted retries, moved to DLQ

@dataclass
class DeliveryAttempt:
    signal_id: str
    user_id: str
    channel: str
    attempt: int
    max_attempts: int = 6
    base_delay_seconds: float = 1.0
    status: DeliveryStatus = DeliveryStatus.PENDING
    error_message: Optional[str] = None
    delivered_at: Optional[datetime] = None

class RetryableDispatcher:
    def __init__(self, kafka: Kafka, dlq: DeadLetterQueue):
        self.kafka = kafka
        self.dlq = dlq

    async def dispatch_with_retry(
        self,
        signal: Signal,
        user_id: str,
        channel: str,
        dispatcher: ChannelDispatcher
    ) -> DeliveryAttempt:
        """Dispatch with exponential backoff retry."""
        attempt = DeliveryAttempt(
            signal_id=signal.signal_id,
            user_id=user_id,
            channel=channel,
            attempt=0
        )

        while attempt.attempt < attempt.max_attempts:
            attempt.attempt += 1

            try:
                await dispatcher.send(signal, user_id)
                attempt.status = DeliveryStatus.DELIVERED
                attempt.delivered_at = datetime.utcnow()
                await self._record_success(attempt)
                return attempt

            except RetryableError as e:
                attempt.status = DeliveryStatus.RETRYING
                attempt.error_message = str(e)

                if attempt.attempt >= attempt.max_attempts:
                    break

                # Exponential backoff: 1s, 2s, 4s, 8s, 16s
                delay = attempt.base_delay_seconds * (2 ** (attempt.attempt - 1))
                await asyncio.sleep(delay)

            except PermanentError as e:
                # Don't retry permanent failures (invalid token, blocked user)
                attempt.error_message = str(e)
                break

        # Exhausted retries - move to DLQ
        attempt.status = DeliveryStatus.FAILED
        await self.dlq.enqueue(attempt, signal)
        return attempt

    async def _record_success(self, attempt: DeliveryAttempt) -> None:
        """Record successful delivery for tracking."""
        key = f"delivery:success:{attempt.signal_id}:{attempt.user_id}:{attempt.channel}"
        await self.kafka.setex(key, 86400, attempt.delivered_at.isoformat())
```

### Dead Letter Queue

Messages that fail after all retry attempts are moved to a dead letter queue for manual inspection and potential reprocessing.

```python
@dataclass
class DLQEntry:
    id: str
    signal_id: str
    user_id: str
    channel: str
    error_message: str
    attempts: int
    first_attempt_at: datetime
    last_attempt_at: datetime
    signal_payload: dict
    status: str = "pending"      # pending, reprocessed, discarded

class DeadLetterQueue:
    def __init__(self, db: Database):
        self.db = db

    async def enqueue(self, attempt: DeliveryAttempt, signal: Signal) -> str:
        """Add failed delivery to DLQ."""
        entry = DLQEntry(
            id=str(uuid4()),
            signal_id=attempt.signal_id,
            user_id=attempt.user_id,
            channel=attempt.channel,
            error_message=attempt.error_message,
            attempts=attempt.attempt,
            first_attempt_at=datetime.utcnow(),
            last_attempt_at=datetime.utcnow(),
            signal_payload=signal.to_dict()
        )

        await self.db.execute("""
            INSERT INTO delivery_dlq
            (id, signal_id, user_id, channel, error_message, attempts,
             first_attempt_at, last_attempt_at, signal_payload, status)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        """, entry.id, entry.signal_id, entry.user_id, entry.channel,
             entry.error_message, entry.attempts, entry.first_attempt_at,
             entry.last_attempt_at, json.dumps(entry.signal_payload), entry.status)

        return entry.id

    async def get_pending(self, limit: int = 100) -> list[DLQEntry]:
        """Get pending DLQ entries for review."""
        rows = await self.db.fetch("""
            SELECT * FROM delivery_dlq
            WHERE status = 'pending'
            ORDER BY last_attempt_at ASC
            LIMIT $1
        """, limit)
        return [DLQEntry(**row) for row in rows]

    async def reprocess(self, entry_id: str) -> bool:
        """Attempt to reprocess a DLQ entry."""
        entry = await self._get_entry(entry_id)
        if not entry:
            return False

        # Reconstruct signal and retry
        signal = Signal.from_dict(entry.signal_payload)
        success = await self._retry_delivery(signal, entry.user_id, entry.channel)

        if success:
            await self._mark_status(entry_id, "reprocessed")
        return success

    async def discard(self, entry_id: str, reason: str) -> None:
        """Mark entry as discarded (won't retry)."""
        await self.db.execute("""
            UPDATE delivery_dlq
            SET status = 'discarded', discard_reason = $2
            WHERE id = $1
        """, entry_id, reason)
```

### DLQ Schema

```sql
CREATE TABLE delivery_dlq (
    id UUID PRIMARY KEY,
    signal_id VARCHAR(255) NOT NULL,
    user_id UUID NOT NULL,
    channel VARCHAR(50) NOT NULL,
    error_message TEXT,
    attempts INTEGER NOT NULL,
    first_attempt_at TIMESTAMP NOT NULL,
    last_attempt_at TIMESTAMP NOT NULL,
    signal_payload JSONB NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',  -- pending, reprocessed, discarded
    discard_reason TEXT,
    reprocessed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_dlq_status ON delivery_dlq(status);
CREATE INDEX idx_dlq_channel ON delivery_dlq(channel);
CREATE INDEX idx_dlq_last_attempt ON delivery_dlq(last_attempt_at);
```

### DLQ Monitoring API

```
GET  /api/admin/dlq                  # List pending DLQ entries
GET  /api/admin/dlq/:id              # Get DLQ entry details
POST /api/admin/dlq/:id/reprocess    # Retry delivery
POST /api/admin/dlq/:id/discard      # Discard entry
GET  /api/admin/dlq/stats            # DLQ statistics by channel
```

---

## Delivery Confirmation and Receipt Tracking

Track delivery status and confirmations for each message sent.

### Delivery Receipt Schema

```sql
CREATE TABLE delivery_receipts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    signal_id VARCHAR(255) NOT NULL,
    user_id UUID NOT NULL,
    channel VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL,         -- pending, sent, delivered, read, failed
    external_message_id VARCHAR(255),    -- Platform-specific message ID
    sent_at TIMESTAMP,
    delivered_at TIMESTAMP,
    read_at TIMESTAMP,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(signal_id, user_id, channel)
);

CREATE INDEX idx_receipts_user ON delivery_receipts(user_id);
CREATE INDEX idx_receipts_signal ON delivery_receipts(signal_id);
CREATE INDEX idx_receipts_status ON delivery_receipts(status);
```

### Receipt Tracker Implementation

```python
class DeliveryTracker:
    def __init__(self, db: Database, metrics: MetricsClient):
        self.db = db
        self.metrics = metrics

    async def create_receipt(
        self,
        signal_id: str,
        user_id: str,
        channel: str
    ) -> str:
        """Create pending delivery receipt."""
        receipt_id = str(uuid4())
        await self.db.execute("""
            INSERT INTO delivery_receipts
            (id, signal_id, user_id, channel, status)
            VALUES ($1, $2, $3, $4, 'pending')
            ON CONFLICT (signal_id, user_id, channel) DO NOTHING
        """, receipt_id, signal_id, user_id, channel)
        return receipt_id

    async def mark_sent(
        self,
        signal_id: str,
        user_id: str,
        channel: str,
        external_id: str
    ) -> None:
        """Mark message as sent with external ID."""
        await self.db.execute("""
            UPDATE delivery_receipts
            SET status = 'sent',
                external_message_id = $4,
                sent_at = NOW(),
                updated_at = NOW()
            WHERE signal_id = $1 AND user_id = $2 AND channel = $3
        """, signal_id, user_id, channel, external_id)

        self.metrics.increment("delivery.sent", tags={"channel": channel})

    async def mark_delivered(
        self,
        signal_id: str,
        user_id: str,
        channel: str
    ) -> None:
        """Mark message as delivered (confirmed by platform)."""
        await self.db.execute("""
            UPDATE delivery_receipts
            SET status = 'delivered',
                delivered_at = NOW(),
                updated_at = NOW()
            WHERE signal_id = $1 AND user_id = $2 AND channel = $3
        """, signal_id, user_id, channel)

        self.metrics.increment("delivery.delivered", tags={"channel": channel})

    async def mark_read(
        self,
        signal_id: str,
        user_id: str,
        channel: str
    ) -> None:
        """Mark message as read (if platform supports read receipts)."""
        await self.db.execute("""
            UPDATE delivery_receipts
            SET status = 'read',
                read_at = NOW(),
                updated_at = NOW()
            WHERE signal_id = $1 AND user_id = $2 AND channel = $3
        """, signal_id, user_id, channel)

        self.metrics.increment("delivery.read", tags={"channel": channel})

    async def mark_failed(
        self,
        signal_id: str,
        user_id: str,
        channel: str,
        error: str,
        retry_count: int
    ) -> None:
        """Mark delivery as failed."""
        await self.db.execute("""
            UPDATE delivery_receipts
            SET status = 'failed',
                error_message = $4,
                retry_count = $5,
                updated_at = NOW()
            WHERE signal_id = $1 AND user_id = $2 AND channel = $3
        """, signal_id, user_id, channel, error, retry_count)

        self.metrics.increment("delivery.failed", tags={"channel": channel})

    async def get_delivery_stats(
        self,
        user_id: str,
        days: int = 7
    ) -> dict:
        """Get delivery statistics for a user."""
        rows = await self.db.fetch("""
            SELECT channel, status, COUNT(*) as count
            FROM delivery_receipts
            WHERE user_id = $1
              AND created_at > NOW() - INTERVAL '%s days'
            GROUP BY channel, status
        """ % days, user_id)

        return self._aggregate_stats(rows)
```

### Delivery Status API

```
GET  /api/user/deliveries                    # User's recent deliveries
GET  /api/user/deliveries/:signal_id         # Delivery status for specific signal
GET  /api/user/deliveries/stats              # Delivery success rate by channel
GET  /api/admin/deliveries/metrics           # System-wide delivery metrics
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

| Channel | Default Limit | Window | Power User Limit |
|---------|---------------|--------|------------------|
| Telegram | 1 per symbol | 5 minutes | 1 per symbol / 2 min |
| Discord | 1 per symbol | 5 minutes | 1 per symbol / 2 min |
| Slack | 1 per symbol | 5 minutes | 1 per symbol / 2 min |
| Push | 10 total | 1 hour | 30 total / 1 hour |

**Note:** Push notification limit increased from 5/hour to 10/hour default, with 30/hour for power users. This ensures high-priority HOT opportunities are not missed while still preventing notification fatigue.

### User Tier Configuration

| Tier | Description | Rate Limit Multiplier |
|------|-------------|----------------------|
| `free` | Default tier | 1x (standard limits) |
| `pro` | Paid subscribers | 2x limits |
| `power` | High-volume traders | 3x limits |

### Implementation

```python
class RateLimiter:
    TIER_MULTIPLIERS = {
        "free": 1.0,
        "pro": 2.0,
        "power": 3.0
    }

    DEFAULT_LIMITS = {
        "telegram": {"per_symbol_seconds": 300, "base_limit": 1},
        "discord": {"per_symbol_seconds": 300, "base_limit": 1},
        "slack": {"per_symbol_seconds": 300, "base_limit": 1},
        "push": {"per_hour": 10, "base_limit": 10}
    }

    def __init__(self, kafka: Kafka, user_service: UserService):
        self.kafka = kafka
        self.user_service = user_service

    async def is_rate_limited(
        self,
        user_id: str,
        channel: str,
        symbol: str,
        window_seconds: int = 300
    ) -> bool:
        # Get user tier for rate limit adjustment
        user_tier = await self.user_service.get_tier(user_id)
        multiplier = self.TIER_MULTIPLIERS.get(user_tier, 1.0)

        # Adjust window based on tier (shorter window = more messages allowed)
        adjusted_window = int(window_seconds / multiplier)

        key = f"ratelimit:{channel}:{user_id}:{symbol}"
        exists = await self.kafka.exists(key)

        if exists:
            return True

        await self.kafka.setex(key, adjusted_window, "1")
        return False

    async def is_push_rate_limited(self, user_id: str) -> bool:
        """Special rate limiting for push notifications (total count, not per-symbol)."""
        user_tier = await self.user_service.get_tier(user_id)
        multiplier = self.TIER_MULTIPLIERS.get(user_tier, 1.0)
        max_per_hour = int(self.DEFAULT_LIMITS["push"]["per_hour"] * multiplier)

        key = f"ratelimit:push:{user_id}:hourly"
        current = await self.kafka.incr(key)

        if current == 1:
            await self.kafka.expire(key, 3600)  # 1 hour TTL

        return current > max_per_hour
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
    is_primary BOOLEAN DEFAULT FALSE,  -- Primary channel for deduplication
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

-- User-level delivery preferences
CREATE TABLE user_delivery_preferences (
    user_id UUID PRIMARY KEY,
    dedup_preference VARCHAR(20) DEFAULT 'primary_only',  -- primary_only, all_enabled, fallback_chain
    primary_channel VARCHAR(50),                          -- User's primary channel
    fallback_order TEXT[],                                -- Channel order for fallback_chain mode
    tier VARCHAR(20) DEFAULT 'free',                      -- free, pro, power
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
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
  # Retry and DLQ settings
  retry:
    max_attempts: 6
    base_delay_seconds: 1.0
    max_delay_seconds: 16.0
    backoff_multiplier: 2.0

  dlq:
    enabled: true
    retention_days: 30
    auto_discard_after_days: 7  # Auto-discard stale entries

  # Cross-channel deduplication
  deduplication:
    enabled: true
    ttl_seconds: 3600           # 1 hour dedup window
    default_preference: "primary_only"  # primary_only, all_enabled, fallback_chain

  # Delivery tracking
  tracking:
    enabled: true
    retention_days: 30

  # Channel-specific settings
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
      per_hour: 10              # Increased from 5 for power users
      power_user_per_hour: 30

  email:
    provider: sendgrid
    api_key: ${SENDGRID_API_KEY}
    from_address: alerts@tradestream.io
```

## Constraints

- Users must opt-in to each channel
- Rate limits prevent spam (tiered by user subscription)
- Configurable minimum opportunity score for alerts
- Quiet hours support per user
- Graceful degradation if channel unavailable
- Cross-channel deduplication prevents duplicate alerts
- Failed deliveries retry with exponential backoff (max 6 attempts, ~31s total)
- Permanently failed messages move to DLQ for manual review
- All delivery attempts tracked for audit and debugging

## Acceptance Criteria

### Core Functionality
- [ ] Telegram bot responds to /signals command
- [ ] Discord webhook posts formatted alerts
- [ ] Users can configure alert preferences
- [ ] Rate limiting prevents spam (1 per symbol per 5 min)
- [ ] Quiet hours respected
- [ ] Minimum opportunity score filter works
- [ ] All channels show consistent signal information (via template engine)

### Retry and Error Handling
- [ ] Failed deliveries retry with exponential backoff
- [ ] Retries stop after 6 attempts (~31 seconds)
- [ ] Failed messages move to DLQ after retry exhaustion
- [ ] DLQ entries can be reprocessed via admin API
- [ ] Permanent errors (invalid token, blocked user) skip retries

### Cross-Channel Deduplication
- [ ] Same signal not sent to multiple channels by default
- [ ] Users can opt-in to receive on all channels
- [ ] Fallback chain mode tries next channel if primary fails

### Delivery Tracking
- [ ] All deliveries create receipt records
- [ ] Receipts track sent/delivered/read status
- [ ] Users can view their delivery history
- [ ] Admins can view system-wide delivery metrics

### Rate Limiting
- [ ] Power users get higher rate limits (3x)
- [ ] Push notifications allow 10/hour (30 for power users)
- [ ] Per-symbol limits enforced across messaging channels

## File Structure

```
services/
├── delivery/
│   ├── __init__.py
│   ├── main.py              # Delivery orchestrator
│   ├── rate_limiter.py      # Rate limiting with tier support
│   ├── retry.py             # Retry with exponential backoff
│   ├── dlq.py               # Dead letter queue
│   ├── deduplication.py     # Cross-channel deduplication
│   ├── tracker.py           # Delivery receipt tracking
│   ├── templates/
│   │   ├── __init__.py
│   │   ├── engine.py        # Template rendering engine
│   │   └── adapters/
│   │       ├── telegram.py
│   │       ├── discord.py
│   │       ├── slack.py
│   │       └── push.py
│   └── preferences.py       # User preferences
├── telegram_bot/
│   ├── main.py
│   ├── handlers.py
│   └── Dockerfile
├── discord_webhook/
│   ├── main.py
│   └── Dockerfile
├── slack_bot/
│   ├── main.py
│   ├── handlers.py
│   └── Dockerfile
└── push_service/
    ├── main.py
    └── Dockerfile
```
