"""Entrypoint for the Sentiment Analysis API service."""

import uvicorn

from services.sentiment_api.app import create_app


def main():
    app = create_app()
    uvicorn.run(app, host="0.0.0.0", port=8080)


if __name__ == "__main__":
    main()
