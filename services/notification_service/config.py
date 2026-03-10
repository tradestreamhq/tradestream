"""Configuration for the notification service."""

import os


def get_config():
    """Load configuration from environment variables."""
    return {
        "redis_host": os.environ.get("REDIS_HOST", "localhost"),
        "redis_port": int(os.environ.get("REDIS_PORT", "6379")),
        "telegram_bot_token": os.environ.get("TELEGRAM_BOT_TOKEN", ""),
        "telegram_chat_id": os.environ.get("TELEGRAM_CHAT_ID", ""),
        "discord_webhook_url": os.environ.get("DISCORD_WEBHOOK_URL", ""),
        "min_score": float(os.environ.get("MIN_SCORE", "0.7")),
        "tiers": os.environ.get("TIERS", ""),
        "symbols": os.environ.get("SYMBOLS", ""),
    }
