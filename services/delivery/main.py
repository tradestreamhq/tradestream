"""Multi-channel delivery service entry point.

Subscribes to Redis Pub/Sub for signals and routes them through
the delivery pipeline: preferences -> deduplication -> rate limiting
-> channel dispatch -> receipt tracking.
"""

import json
import signal
import sys

import redis
from absl import app, flags, logging

from services.delivery.channels.discord import DiscordDeliveryChannel
from services.delivery.channels.email import EmailDeliveryChannel
from services.delivery.channels.slack import SlackDeliveryChannel
from services.delivery.channels.sms import SMSDeliveryChannel
from services.delivery.channels.telegram import TelegramDeliveryChannel
from services.delivery.channels.webhook import WebhookDeliveryChannel
from services.delivery.deduplication import CrossChannelDeduplicator
from services.delivery.preferences import PreferenceStore
from services.delivery.rate_limiter import DeliveryRateLimiter
from services.delivery.router import DeliveryRouter
from services.delivery.tracker import DeliveryTracker
from services.shared.structured_logger import StructuredLogger

FLAGS = flags.FLAGS

flags.DEFINE_string("redis_host", "localhost", "Redis host.")
flags.DEFINE_integer("redis_port", 6379, "Redis port.")
flags.DEFINE_string("telegram_bot_token", "", "Telegram bot token.")
flags.DEFINE_string("twilio_account_sid", "", "Twilio account SID.")
flags.DEFINE_string("twilio_auth_token", "", "Twilio auth token.")
flags.DEFINE_string("twilio_from_number", "", "Twilio sender phone number.")
flags.DEFINE_string("smtp_host", "", "SMTP host for email delivery.")
flags.DEFINE_integer("smtp_port", 587, "SMTP port.")
flags.DEFINE_string("smtp_username", "", "SMTP username.")
flags.DEFINE_string("smtp_password", "", "SMTP password.")
flags.DEFINE_string("email_from", "alerts@tradestream.io", "Email from address.")
flags.DEFINE_string("webhook_signing_secret", "", "Webhook HMAC signing secret.")

_shutdown = False
_log = StructuredLogger(service_name="delivery_service")


def _handle_shutdown(signum, frame):
    global _shutdown
    _log.info("Received shutdown signal", signum=signum)
    _shutdown = True


def _build_channels() -> dict:
    """Build available delivery channel instances from flags."""
    channels = {}

    if FLAGS.telegram_bot_token:
        channels["telegram"] = TelegramDeliveryChannel(FLAGS.telegram_bot_token)
        _log.info("Telegram channel enabled.")

    channels["discord"] = DiscordDeliveryChannel()
    _log.info("Discord channel enabled.")

    channels["slack"] = SlackDeliveryChannel()
    _log.info("Slack channel enabled.")

    channels["webhook"] = WebhookDeliveryChannel(FLAGS.webhook_signing_secret)
    _log.info("Webhook channel enabled.")

    if FLAGS.smtp_host:
        channels["email"] = EmailDeliveryChannel(
            smtp_host=FLAGS.smtp_host,
            smtp_port=FLAGS.smtp_port,
            username=FLAGS.smtp_username,
            password=FLAGS.smtp_password,
            from_addr=FLAGS.email_from,
        )
        _log.info("Email channel enabled.")

    if FLAGS.twilio_account_sid and FLAGS.twilio_auth_token:
        channels["sms"] = SMSDeliveryChannel(
            account_sid=FLAGS.twilio_account_sid,
            auth_token=FLAGS.twilio_auth_token,
            from_number=FLAGS.twilio_from_number,
        )
        _log.info("SMS channel enabled.")

    return channels


def main(argv):
    del argv
    logging.set_verbosity(logging.INFO)

    signal.signal(signal.SIGINT, _handle_shutdown)
    signal.signal(signal.SIGTERM, _handle_shutdown)

    _log.new_correlation_id()

    redis_client = redis.Redis(
        host=FLAGS.redis_host, port=FLAGS.redis_port, decode_responses=True
    )
    redis_client.ping()
    _log.info("Connected to Redis.", host=FLAGS.redis_host, port=FLAGS.redis_port)

    channels = _build_channels()
    if not channels:
        _log.warning("No delivery channels configured. Exiting.")
        sys.exit(0)

    preference_store = PreferenceStore(redis_client)
    deduplicator = CrossChannelDeduplicator(redis_client)
    rate_limiter = DeliveryRateLimiter(redis_client)
    tracker = DeliveryTracker(redis_client)

    router = DeliveryRouter(
        channels=channels,
        preference_store=preference_store,
        deduplicator=deduplicator,
        rate_limiter=rate_limiter,
        tracker=tracker,
    )

    pubsub = redis_client.pubsub()
    pubsub.psubscribe("signals:*")

    _log.info(
        "Delivery service started. Listening for signals.",
        channels=list(channels.keys()),
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

        # Get list of subscribed user IDs from Redis
        user_ids = _get_subscribed_users(redis_client, signal_data)

        if not user_ids:
            continue

        _log.info(
            "Routing signal to users",
            signal_id=signal_id,
            user_count=len(user_ids),
        )

        results = router.route_signal_to_all_users(signal_data, user_ids)

        for user_id, user_results in results.items():
            for result in user_results:
                if result.success:
                    _log.info(
                        "Signal delivered",
                        signal_id=signal_id,
                        user_id=user_id,
                        channel=result.channel,
                    )
                else:
                    _log.warning(
                        "Signal delivery failed",
                        signal_id=signal_id,
                        user_id=user_id,
                        channel=result.channel,
                        error=result.error,
                    )

    pubsub.close()
    redis_client.close()
    _log.info("Delivery service shut down.")


def _get_subscribed_users(redis_client, signal_data: dict) -> list[str]:
    """Get user IDs subscribed to receive this signal.

    Looks up users who have delivery preferences configured.
    Uses a Redis set of user IDs that have registered for delivery.
    """
    user_ids = redis_client.smembers("delivery:subscribed_users")
    return list(user_ids) if user_ids else []


if __name__ == "__main__":
    app.run(main)
