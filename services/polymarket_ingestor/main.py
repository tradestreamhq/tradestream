"""Polymarket Data Ingestor service.

Fetches prediction market data from the Polymarket CLOB API and publishes
it to Kafka topics for downstream consumption. Supports both market metadata
ingestion (periodic) and trade/orderbook polling.
"""

import os
import signal
import sys
import json

from absl import app
from absl import flags
from absl import logging

from services.polymarket_ingestor.polymarket_api_client import PolymarketApiClient
from services.polymarket_ingestor.kafka_producer import PolymarketKafkaProducer
from google.protobuf.timestamp_pb2 import Timestamp
from protos.polymarket_pb2 import (
    PolymarketMarket,
    PolymarketToken,
    PolymarketTrade,
    PolymarketOrderBook,
    PriceLevel,
)

FLAGS = flags.FLAGS

# Run mode
flags.DEFINE_string(
    "run_mode",
    os.getenv("RUN_MODE", "wet"),
    "Run mode: 'wet' for live, 'dry' for dry run (no Kafka publishing).",
)

# Polymarket API
flags.DEFINE_string(
    "polymarket_api_url",
    os.getenv("POLYMARKET_API_URL", "https://clob.polymarket.com"),
    "Base URL for the Polymarket CLOB API.",
)
flags.DEFINE_integer(
    "api_request_timeout",
    int(os.getenv("API_REQUEST_TIMEOUT", "30")),
    "Timeout in seconds for API requests.",
)
flags.DEFINE_integer(
    "max_pages",
    int(os.getenv("MAX_PAGES", "10")),
    "Maximum number of pages to fetch when paginating markets.",
)

# Kafka
flags.DEFINE_string(
    "kafka_bootstrap_servers",
    os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
    "Kafka bootstrap servers.",
)
flags.DEFINE_string(
    "kafka_security_protocol",
    os.getenv("KAFKA_SECURITY_PROTOCOL", "SSL"),
    "Kafka security protocol.",
)
flags.DEFINE_string(
    "kafka_ssl_ca_location",
    os.getenv("KAFKA_SSL_CA_LOCATION", ""),
    "Path to Kafka SSL CA certificate.",
)
flags.DEFINE_string(
    "kafka_ssl_cert_location",
    os.getenv("KAFKA_SSL_CERT_LOCATION", ""),
    "Path to Kafka SSL client certificate.",
)
flags.DEFINE_string(
    "kafka_ssl_key_location",
    os.getenv("KAFKA_SSL_KEY_LOCATION", ""),
    "Path to Kafka SSL client key.",
)

# Kafka topics
flags.DEFINE_string(
    "kafka_topic_markets",
    os.getenv("KAFKA_TOPIC_MARKETS", "polymarket-markets"),
    "Kafka topic for market metadata.",
)
flags.DEFINE_string(
    "kafka_topic_trades",
    os.getenv("KAFKA_TOPIC_TRADES", "polymarket-trades"),
    "Kafka topic for trade events.",
)
flags.DEFINE_string(
    "kafka_topic_orderbook",
    os.getenv("KAFKA_TOPIC_ORDERBOOK", "polymarket-orderbook"),
    "Kafka topic for order book snapshots.",
)

# Ingestion config
flags.DEFINE_integer(
    "orderbook_top_n",
    int(os.getenv("ORDERBOOK_TOP_N", "10")),
    "Number of top price levels to capture from order book.",
)

_shutdown_requested = False


def _signal_handler(signum, frame):
    global _shutdown_requested
    logging.info(f"Received signal {signum}, shutting down gracefully...")
    _shutdown_requested = True


def _parse_market_to_proto(market_data: dict) -> PolymarketMarket:
    """Convert raw API market data to protobuf message."""
    market = PolymarketMarket()
    market.market_id = str(market_data.get("condition_id", ""))
    market.condition_id = str(market_data.get("condition_id", ""))
    market.question = str(market_data.get("question", ""))
    market.description = str(market_data.get("description", ""))[:1000]
    market.resolution_source = str(market_data.get("market_slug", ""))
    market.active = bool(market_data.get("active", False))
    market.closed = bool(market_data.get("closed", False))

    volume_str = market_data.get("volume", "0")
    try:
        market.volume = float(volume_str)
    except (ValueError, TypeError):
        market.volume = 0.0

    liquidity_str = market_data.get("liquidity", "0")
    try:
        market.liquidity = float(liquidity_str)
    except (ValueError, TypeError):
        market.liquidity = 0.0

    end_date_str = market_data.get("end_date_iso")
    if end_date_str:
        try:
            from datetime import datetime

            dt = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
            market.end_date.FromDatetime(dt)
        except (ValueError, AttributeError):
            pass

    tokens = market_data.get("tokens", [])
    for token_data in tokens:
        token = market.tokens.add()
        token.token_id = str(token_data.get("token_id", ""))
        token.outcome = str(token_data.get("outcome", ""))
        try:
            token.price = float(token_data.get("price", 0))
        except (ValueError, TypeError):
            token.price = 0.0

    return market


def _parse_orderbook_to_proto(
    token_id: str, market_id: str, book_data: dict
) -> PolymarketOrderBook:
    """Convert raw API order book data to protobuf message."""
    orderbook = PolymarketOrderBook()
    orderbook.market_id = market_id
    orderbook.asset_id = token_id

    ts = Timestamp()
    from datetime import datetime, timezone

    ts.FromDatetime(datetime.now(timezone.utc))
    orderbook.timestamp.CopyFrom(ts)

    top_n = FLAGS.orderbook_top_n
    for bid in (book_data.get("bids", []))[:top_n]:
        level = orderbook.bids.add()
        level.price = float(bid.get("price", 0))
        level.size = float(bid.get("size", 0))

    for ask in (book_data.get("asks", []))[:top_n]:
        level = orderbook.asks.add()
        level.price = float(ask.get("price", 0))
        level.size = float(ask.get("size", 0))

    return orderbook


def _ingest_markets(api_client: PolymarketApiClient, kafka_producer=None):
    """Fetch and publish all active market metadata."""
    logging.info("Starting market metadata ingestion...")
    markets = api_client.get_all_active_markets(max_pages=FLAGS.max_pages)
    logging.info(f"Fetched {len(markets)} markets from Polymarket API.")

    published_count = 0
    for market_data in markets:
        if _shutdown_requested:
            logging.info("Shutdown requested, stopping market ingestion.")
            break

        market_proto = _parse_market_to_proto(market_data)
        if FLAGS.run_mode == "dry":
            logging.info(
                f"[DRY] Market: {market_proto.question[:80]} "
                f"(volume={market_proto.volume:.2f})"
            )
        elif kafka_producer:
            kafka_producer.publish(
                FLAGS.kafka_topic_markets,
                market_proto.SerializeToString(),
                key=market_proto.market_id,
            )
        published_count += 1

    logging.info(f"Published {published_count} markets to Kafka.")
    return published_count


def _ingest_orderbooks(
    api_client: PolymarketApiClient, markets: list, kafka_producer=None
):
    """Fetch and publish order book snapshots for active markets."""
    logging.info("Starting order book ingestion...")
    published_count = 0

    for market_data in markets:
        if _shutdown_requested:
            logging.info("Shutdown requested, stopping orderbook ingestion.")
            break

        condition_id = market_data.get("condition_id", "")
        tokens = market_data.get("tokens", [])
        for token_data in tokens:
            token_id = token_data.get("token_id", "")
            if not token_id:
                continue
            try:
                book_data = api_client.get_order_book(token_id)
                orderbook_proto = _parse_orderbook_to_proto(
                    token_id, condition_id, book_data
                )

                if FLAGS.run_mode == "dry":
                    bids_count = len(orderbook_proto.bids)
                    asks_count = len(orderbook_proto.asks)
                    logging.info(
                        f"[DRY] OrderBook: market={condition_id[:16]}... "
                        f"token={token_id[:16]}... "
                        f"bids={bids_count} asks={asks_count}"
                    )
                elif kafka_producer:
                    kafka_producer.publish(
                        FLAGS.kafka_topic_orderbook,
                        orderbook_proto.SerializeToString(),
                        key=token_id,
                    )
                published_count += 1
            except Exception as e:
                logging.warning(
                    f"Failed to fetch orderbook for token {token_id}: {e}"
                )

    logging.info(f"Published {published_count} orderbook snapshots to Kafka.")
    return published_count


def run():
    """Main run function for the Polymarket ingestor."""
    logging.info("Polymarket Data Ingestor starting...")
    logging.info(f"Run mode: {FLAGS.run_mode}")
    logging.info(f"API URL: {FLAGS.polymarket_api_url}")

    api_client = PolymarketApiClient(
        base_url=FLAGS.polymarket_api_url,
        request_timeout=FLAGS.api_request_timeout,
    )

    kafka_producer = None
    if FLAGS.run_mode == "wet":
        ssl_ca = FLAGS.kafka_ssl_ca_location or None
        ssl_cert = FLAGS.kafka_ssl_cert_location or None
        ssl_key = FLAGS.kafka_ssl_key_location or None
        kafka_producer = PolymarketKafkaProducer(
            bootstrap_servers=FLAGS.kafka_bootstrap_servers,
            security_protocol=FLAGS.kafka_security_protocol,
            ssl_cafile=ssl_ca,
            ssl_certfile=ssl_cert,
            ssl_keyfile=ssl_key,
        )

    try:
        # Phase 1: Ingest market metadata
        market_count = _ingest_markets(api_client, kafka_producer)

        # Phase 2: Ingest order book snapshots for active markets
        if not _shutdown_requested:
            markets = api_client.get_all_active_markets(max_pages=FLAGS.max_pages)
            active_markets = [m for m in markets if m.get("active") and not m.get("closed")]
            # Limit orderbook fetching to avoid API rate limits
            orderbook_markets = active_markets[:50]
            _ingest_orderbooks(api_client, orderbook_markets, kafka_producer)

        logging.info("Polymarket Data Ingestor completed successfully.")
    except Exception as e:
        logging.error(f"Polymarket Data Ingestor failed: {e}")
        raise
    finally:
        api_client.close()
        if kafka_producer:
            kafka_producer.close()


def main(argv):
    del argv  # Unused.
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)
    logging.set_verbosity(logging.INFO)
    run()


if __name__ == "__main__":
    app.run(main)
