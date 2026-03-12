"""Entry point for the alert router service."""

import uvicorn

from services.alert_router.app import create_app
from services.alert_router.config import get_config


def main():
    config = get_config()
    app = create_app()
    uvicorn.run(app, host=config["host"], port=config["port"])


if __name__ == "__main__":
    main()
