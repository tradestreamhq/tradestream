"""Entry point for the Market Sentiment Signal Source service."""

import signal
import sys

import uvicorn
from absl import app as absl_app
from absl import flags, logging

from services.market_sentiment.aggregator import SentimentDataFetcher
from services.market_sentiment.app import create_app
from services.market_sentiment.signal_generator import SentimentMomentumTracker
from services.shared.structured_logger import StructuredLogger

FLAGS = flags.FLAGS

flags.DEFINE_string("host", "0.0.0.0", "Host to bind the HTTP server to.")
flags.DEFINE_integer("port", 8090, "Port for the HTTP server.")
flags.DEFINE_string(
    "fear_greed_url",
    "https://api.alternative.me/fng/",
    "Fear & Greed Index API URL.",
)
flags.DEFINE_integer(
    "momentum_window", 10, "Number of readings to keep for momentum tracking."
)

_log = StructuredLogger(service_name="market_sentiment")


def _handle_shutdown(signum, frame):
    _log.info("Received shutdown signal", signum=signum)
    sys.exit(0)


def main(argv):
    del argv
    logging.set_verbosity(logging.INFO)

    signal.signal(signal.SIGINT, _handle_shutdown)
    signal.signal(signal.SIGTERM, _handle_shutdown)

    fetcher = SentimentDataFetcher(fear_greed_url=FLAGS.fear_greed_url)
    momentum = SentimentMomentumTracker(window_size=FLAGS.momentum_window)

    _log.info(
        "Market Sentiment Signal Source starting",
        host=FLAGS.host,
        port=FLAGS.port,
    )

    fastapi_app = create_app(fetcher=fetcher, momentum_tracker=momentum)
    uvicorn.run(fastapi_app, host=FLAGS.host, port=FLAGS.port, log_level="info")


if __name__ == "__main__":
    absl_app.run(main)
