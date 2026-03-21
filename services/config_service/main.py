"""Entrypoint for the Config API service."""

import logging
import os

import uvicorn

from services.config_service.app import create_app
from services.config_service.config_service import ConfigService

logging.basicConfig(level=logging.INFO)


def main():
    config_dir = os.environ.get("CONFIG_DIR", None)
    svc = ConfigService(config_dir=config_dir)
    svc.load()
    svc.start_watching()

    app = create_app(svc)

    host = os.environ.get("API_HOST", "0.0.0.0")
    port = int(os.environ.get("API_PORT", "8080"))
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
