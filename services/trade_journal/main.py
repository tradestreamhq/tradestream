"""Entry point for the Trade Journal service."""

import signal
import sys

from absl import app, flags, logging

from services.trade_journal.journal import TradeJournal
from services.trade_journal.service import create_app

FLAGS = flags.FLAGS

flags.DEFINE_integer("port", 8095, "HTTP server port")


def main(argv):
    del argv
    logging.set_verbosity(logging.INFO)

    journal = TradeJournal()
    flask_app = create_app(journal=journal)

    def shutdown_handler(signum, frame):
        logging.info("Received signal %d, shutting down...", signum)
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    logging.info("Trade Journal service starting on port %d", FLAGS.port)
    flask_app.run(host="0.0.0.0", port=FLAGS.port)


if __name__ == "__main__":
    app.run(main)
