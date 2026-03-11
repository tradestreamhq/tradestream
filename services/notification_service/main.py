"""Entry point for the Notification Service.

Subscribes to Redis Pub/Sub signal channels and forwards
high-confidence signals to configured messaging platforms.
"""

import json
import signal
import sys

import redis
from absl import app, flags, logging

from services.notification_service.config import get_config
from services.notification_service.discord_sender import DiscordSender
from services.notification_service.telegram_sender import TelegramSender
from services.shared.structured_logger import StructuredLogger

FLAGS = flags.FLAGS

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


def main(argv):
    del argv
    logging.set_verbosity(logging.INFO)

    signal.signal(signal.SIGINT, _handle_shutdown)
    signal.signal(signal.SIGTERM, _handle_shutdown)

    _log.new_correlation_id()

    config = get_config()

    redis_host = config["redis_host"]
    redis_port = config["redis_port"]
    min_score = config["min_score"]
    tiers = [t.strip() for t in config["tiers"].split(",") if t.strip()]

    senders = []

    if config["telegram_bot_token"] and config["telegram_chat_id"]:
        senders.append(
            TelegramSender(config["telegram_bot_token"], config["telegram_chat_id"])
        )
        _log.info("Telegram sender enabled.")
    else:
        _log.info("Telegram not configured, skipping.")

    if config["discord_webhook_url"]:
        senders.append(DiscordSender(config["discord_webhook_url"]))
        _log.info("Discord sender enabled.")
    else:
        _log.info("Discord not configured, skipping.")

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

    pubsub = client.pubsub()
    if "signals:*" in channels:
        pubsub.psubscribe("signals:*")
    else:
        pubsub.subscribe(*channels)

    _log.info("Notification service started. Listening for signals.")

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

        if not _passes_filter(signal_data, min_score, tiers):
            _log.info(
                "Signal filtered out",
                action=signal_data.get("action"),
                symbol=signal_data.get("symbol"),
                confidence=signal_data.get("confidence", 0),
            )
            continue

        _log.info(
            "Forwarding signal",
            action=signal_data.get("action"),
            symbol=signal_data.get("symbol"),
            confidence=signal_data.get("confidence", 0),
        )

        for sender in senders:
            try:
                sender.send_signal(signal_data)
            except Exception as e:
                _log.error(
                    "Sender failed",
                    sender=type(sender).__name__,
                    error=str(e),
                )

    pubsub.close()
    client.close()
    _log.info("Notification service shut down.")


if __name__ == "__main__":
    app.run(main)
