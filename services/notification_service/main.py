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

FLAGS = flags.FLAGS

_shutdown = False


def _handle_shutdown(signum, frame):
    global _shutdown
    logging.info("Received signal %d, shutting down...", signum)
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
        logging.info("Telegram sender enabled.")
    else:
        logging.info("Telegram not configured, skipping.")

    if config["discord_webhook_url"]:
        senders.append(DiscordSender(config["discord_webhook_url"]))
        logging.info("Discord sender enabled.")
    else:
        logging.info("Discord not configured, skipping.")

    if not senders:
        logging.warning("No notification channels configured. Exiting.")
        sys.exit(0)

    symbols = [s.strip() for s in config["symbols"].split(",") if s.strip()]
    if symbols:
        channels = [f"signals:{s}" for s in symbols]
    else:
        channels = ["signals:*"]

    logging.info(
        "Connecting to Redis at %s:%d, subscribing to %s",
        redis_host,
        redis_port,
        channels,
    )

    client = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)
    client.ping()
    logging.info("Connected to Redis.")

    pubsub = client.pubsub()
    if "signals:*" in channels:
        pubsub.psubscribe("signals:*")
    else:
        pubsub.subscribe(*channels)

    logging.info("Notification service started. Listening for signals...")

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
            logging.warning("Failed to parse signal JSON: %s", data[:200])
            continue

        if not _passes_filter(signal_data, min_score, tiers):
            logging.info(
                "Signal filtered out: %s %s (confidence=%.2f)",
                signal_data.get("action"),
                signal_data.get("symbol"),
                signal_data.get("confidence", 0),
            )
            continue

        logging.info(
            "Forwarding signal: %s %s (confidence=%.2f)",
            signal_data.get("action"),
            signal_data.get("symbol"),
            signal_data.get("confidence", 0),
        )

        for sender in senders:
            try:
                sender.send_signal(signal_data)
            except Exception as e:
                logging.error("Sender %s failed: %s", type(sender).__name__, e)

    pubsub.close()
    client.close()
    logging.info("Notification service shut down.")


if __name__ == "__main__":
    app.run(main)
