"""
Usage API entry point.
"""

import os

import uvicorn

from services.usage_api.app import create_app


def main():
    app = create_app()
    host = os.environ.get("API_HOST", "0.0.0.0")
    port = int(os.environ.get("API_PORT", "8080"))
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
