"""Configuration for the notification service."""

import os


def get_config():
    """Load configuration from environment variables."""
    return {
        # Redis
        "redis_host": os.environ.get("REDIS_HOST", "localhost"),
        "redis_port": int(os.environ.get("REDIS_PORT", "6379")),
        # Signal filtering
        "min_score": float(os.environ.get("MIN_SCORE", "0.7")),
        "tiers": os.environ.get("TIERS", ""),
        "symbols": os.environ.get("SYMBOLS", ""),
        # Telegram
        "telegram_bot_token": os.environ.get("TELEGRAM_BOT_TOKEN", ""),
        "telegram_chat_id": os.environ.get("TELEGRAM_CHAT_ID", ""),
        # Discord
        "discord_webhook_url": os.environ.get("DISCORD_WEBHOOK_URL", ""),
        # Slack
        "slack_webhook_url": os.environ.get("SLACK_WEBHOOK_URL", ""),
        # Webhook (generic HTTP POST)
        "webhook_url": os.environ.get("WEBHOOK_URL", ""),
        "webhook_signing_secret": os.environ.get("WEBHOOK_SIGNING_SECRET", ""),
        # Email
        "email_smtp_host": os.environ.get("EMAIL_SMTP_HOST", ""),
        "email_smtp_port": int(os.environ.get("EMAIL_SMTP_PORT", "587")),
        "email_username": os.environ.get("EMAIL_USERNAME", ""),
        "email_password": os.environ.get("EMAIL_PASSWORD", ""),
        "email_from": os.environ.get("EMAIL_FROM", ""),
        "email_to": os.environ.get("EMAIL_TO", ""),  # comma-separated
        "email_use_tls": os.environ.get("EMAIL_USE_TLS", "true").lower() == "true",
        # Notification history
        "enable_history": os.environ.get("ENABLE_HISTORY", "true").lower() == "true",
    }
