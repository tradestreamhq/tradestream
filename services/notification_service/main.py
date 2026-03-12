"""Entry point for the Notification Service.

Subscribes to Redis Pub/Sub signal channels and forwards
high-confidence signals to configured messaging platforms.

Supports multiple delivery channels:
  - Telegram bot
  - Discord webhook
  - Slack incoming webhook
  - Generic HTTP webhook (with HMAC signing)
  - Email (SMTP)

Tracks notification delivery history in Redis.
"""

import json
import signal
import sys

import redis
from absl import app, flags, logging

from services.notification_service.config import get_config
from services.notification_service.discord_sender import DiscordSender
from services.notification_service.email_sender import EmailSender
from services.notification_service.notification_history import NotificationHistory
from services.notification_service.slack_sender import SlackSender
from services.notification_service.telegram_sender import TelegramSender
from services.notification_service.webhook_sender import WebhookSender
from services.shared.structured_logger import StructuredLogger

FLAGS = flags.FLAGS

flags.DEFINE_string("redis_host", None, "Redis host (overrides REDIS_HOST env var).")
flags.DEFINE_integer("redis_port", None, "Redis port (overrides REDIS_PORT env var).")

_shutdown = False

_log = StructuredLogger(service_name="notification_service")


def _handle_shutdown(signum, frame):
    global _shutdown
    _log.info("Received shutdown signal", signum=signum)
    _shutdown = True


def _passes_filter(signal_data: dict, min_score: float, tiers: list[str]) -> bool:
    """Check if a signal passes the configured filters."""
    confidence = signal_data.get("confidence", 0)
    if confidence < min_score:
        return False
    if tiers:
        tier = signal_data.get("tier", "")
        if tier and tier not in tiers:
            return False
    return True


def _build_senders(config: dict) -> list[tuple[str, object]]:
    """Build sender instances from configuration.

    Returns a list of (channel_name, sender) tuples.
    """
    senders = []

    if config["telegram_bot_token"] and config["telegram_chat_id"]:
        senders.append(
            ("telegram", TelegramSender(config["telegram_bot_token"], config["telegram_chat_id"]))
        )
        _log.info("Telegram sender enabled.")

    if config["discord_webhook_url"]:
        senders.append(("discord", DiscordSender(config["discord_webhook_url"])))
        _log.info("Discord sender enabled.")

    if config["slack_webhook_url"]:
        senders.append(("slack", SlackSender(config["slack_webhook_url"])))
        _log.info("Slack sender enabled.")

    if config["webhook_url"]:
        senders.append(
            (
                "webhook",
                WebhookSender(config["webhook_url"], config["webhook_signing_secret"]),
            )
        )
        _log.info("Webhook sender enabled.")

    if config["email_smtp_host"] and config["email_to"]:
        to_addrs = [a.strip() for a in config["email_to"].split(",") if a.strip()]
        senders.append(
            (
                "email",
                EmailSender(
                    smtp_host=config["email_smtp_host"],
                    smtp_port=config["email_smtp_port"],
                    username=config["email_username"],
                    password=config["email_password"],
                    from_addr=config["email_from"],
                    to_addrs=to_addrs,
                    use_tls=config["email_use_tls"],
                ),
            )
        )
        _log.info("Email sender enabled.")

    return senders


def main(argv):
    del argv
    logging.set_verbosity(logging.INFO)

    signal.signal(signal.SIGINT, _handle_shutdown)
    signal.signal(signal.SIGTERM, _handle_shutdown)

    _log.new_correlation_id()

    config = get_config()

    redis_host = FLAGS.redis_host or config["redis_host"]
    redis_port = FLAGS.redis_port or config["redis_port"]
    min_score = config["min_score"]
    tiers = [t.strip() for t in config["tiers"].split(",") if t.strip()]

    senders = _build_senders(config)

    if not senders:
        _log.warning("No notification channels configured. Exiting.")
        sys.exit(0)

    symbols = [s.strip() for s in config["symbols"].split(",") if s.strip()]
    if symbols:
        channels = [f"signals:{s}" for s in symbols]
    else:
        channels = ["signals:*"]

    _log.info(
        "Connecting to Redis",
        host=redis_host,
        port=redis_port,
        channels=channels,
    )

    client = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)
    client.ping()
    _log.info("Connected to Redis.")

    history = NotificationHistory(client) if config["enable_history"] else None

    pubsub = client.pubsub()
    if "signals:*" in channels:
        pubsub.psubscribe("signals:*")
    else:
        pubsub.subscribe(*channels)

    _log.info(
        "Notification service started. Listening for signals.",
        channels_count=len(senders),
        history_enabled=config["enable_history"],
    )

    while not _shutdown:
        message = pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
        if message is None:
            continue

        data = message.get("data")
        if not data or not isinstance(data, str):
            continue

        try:
            signal_data = json.loads(data)
        except json.JSONDecodeError:
            _log.warning("Failed to parse signal JSON", raw=data[:200])
            continue

        signal_id = signal_data.get("signal_id", "unknown")

        if not _passes_filter(signal_data, min_score, tiers):
            _log.info(
                "Signal filtered out",
                signal_id=signal_id,
                action=signal_data.get("action"),
                symbol=signal_data.get("symbol"),
                confidence=signal_data.get("confidence", 0),
            )
            if history:
                reason = f"confidence={signal_data.get('confidence', 0)} < {min_score}"
                history.record_filtered(signal_id, reason, signal_data)
            continue

        _log.info(
            "Forwarding signal",
            signal_id=signal_id,
            action=signal_data.get("action"),
            symbol=signal_data.get("symbol"),
            confidence=signal_data.get("confidence", 0),
            channels=[name for name, _ in senders],
        )

        for channel_name, sender in senders:
            try:
                success = sender.send_signal(signal_data)
                if history:
                    history.record_delivery(
                        signal_id, channel_name, success, signal_data
                    )
            except Exception as e:
                _log.error(
                    "Sender failed",
                    sender=channel_name,
                    error=str(e),
                )
                if history:
                    history.record_delivery(
                        signal_id, channel_name, False, signal_data, error=str(e)
                    )

    pubsub.close()
    client.close()
    _log.info("Notification service shut down.")


if __name__ == "__main__":
    app.run(main)
