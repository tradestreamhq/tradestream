"""Entry point for the Strategy Graph API service."""

import uvicorn
from absl import app as absl_app
from absl import flags

from services.strategy_graph.app import create_app

FLAGS = flags.FLAGS
flags.DEFINE_string("host", "0.0.0.0", "API host")
flags.DEFINE_integer("port", 8090, "API port")


def main(argv):
    del argv
    application = create_app()
    uvicorn.run(application, host=FLAGS.host, port=FLAGS.port)


if __name__ == "__main__":
    absl_app.run(main)
