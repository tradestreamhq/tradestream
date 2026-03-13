"""Entry point for the Exchange Connector API service."""

from absl import app as absl_app
from absl import flags
import uvicorn

from services.exchange_connector.app import create_app
from services.exchange_connector.mock_connector import MockExchangeConnector
from services.exchange_connector.registry import ExchangeRegistry

FLAGS = flags.FLAGS
flags.DEFINE_integer("port", 8080, "Port to listen on")
flags.DEFINE_string("host", "0.0.0.0", "Host to bind to")


def main(argv):
    del argv
    registry = ExchangeRegistry()
    registry.register(MockExchangeConnector(exchange_name="mock"))
    application = create_app(registry)
    uvicorn.run(application, host=FLAGS.host, port=FLAGS.port)


if __name__ == "__main__":
    absl_app.run(main)
