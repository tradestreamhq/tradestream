"""Entrypoint for the Sentiment Analysis API service."""

import os

import uvicorn

from services.sentiment_api.app import create_app
from services.sentiment_api.data_provider import ExchangeDataProvider


def main():
    provider = ExchangeDataProvider(
        exchange_id=os.environ.get("EXCHANGE_ID", "coinbasepro"),
    )
    app = create_app(provider)
    uvicorn.run(
        app,
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "8080")),
    )


if __name__ == "__main__":
    main()
