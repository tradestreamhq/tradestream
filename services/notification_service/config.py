"""Configuration for the notification service."""

import os

from services.shared.config import get_redis_config


def get_config():
    """Load configuration from environment variables."""
    redis_cfg = get_redis_config()
    return {
        "redis_host": redis_cfg["host"],
        "redis_port": redis_cfg["port"],
        "telegram_bot_token": os.environ.get("TELEGRAM_BOT_TOKEN", ""),
        "telegram_chat_id": os.environ.get("TELEGRAM_CHAT_ID", ""),
        "discord_webhook_url": os.environ.get("DISCORD_WEBHOOK_URL", ""),
        "min_score": float(os.environ.get("MIN_SCORE", "0.7")),
        "tiers": os.environ.get("TIERS", ""),
        "symbols": os.environ.get("SYMBOLS", ""),
    }
