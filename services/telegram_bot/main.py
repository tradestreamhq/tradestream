"""Telegram bot entry point — runs long-polling loop."""

import asyncio
import logging
import os

import asyncpg

from services.telegram_bot.bot import TelegramSignalBot

logger = logging.getLogger(__name__)


async def _create_pool() -> asyncpg.Pool:
    return await asyncpg.create_pool(
        host=os.environ.get("POSTGRES_HOST", "localhost"),
        port=int(os.environ.get("POSTGRES_PORT", "5432")),
        database=os.environ.get("POSTGRES_DATABASE", ""),
        user=os.environ.get("POSTGRES_USERNAME", "postgres"),
        password=os.environ.get("POSTGRES_PASSWORD", ""),
        min_size=2,
        max_size=5,
    )


async def poll_loop(bot: TelegramSignalBot):
    """Long-polling loop that processes incoming Telegram messages."""
    offset = None
    logger.info("Starting Telegram bot polling loop")
    while True:
        updates = bot.get_updates(offset=offset)
        for update in updates:
            offset = update["update_id"] + 1
            message = update.get("message", {})
            text = message.get("text", "")
            chat_id = str(message.get("chat", {}).get("id", ""))

            if not chat_id or not text:
                continue

            if text.startswith("/"):
                response = await bot.handle_command(chat_id, text)
                bot.send_message(chat_id, response)


def main():
    logging.basicConfig(level=logging.INFO)
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN environment variable is required")
        return

    loop = asyncio.get_event_loop()
    pool = loop.run_until_complete(_create_pool())
    bot = TelegramSignalBot(bot_token=token, db_pool=pool)
    loop.run_until_complete(poll_loop(bot))


if __name__ == "__main__":
    main()
