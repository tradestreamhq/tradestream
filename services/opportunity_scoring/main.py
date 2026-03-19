"""Entry point for the Opportunity Scoring Engine."""

import os

import uvicorn

from services.opportunity_scoring.app import create_app
from services.opportunity_scoring.lifecycle import OpportunityTracker


def main():
    tracker = OpportunityTracker()
    app = create_app(tracker)
    host = os.environ.get("API_HOST", "0.0.0.0")
    port = int(os.environ.get("API_PORT", "8080"))
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
