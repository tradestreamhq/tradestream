"""Shared configuration utilities for environment variable validation."""

import logging
import os
import sys
from typing import List

logger = logging.getLogger(__name__)


def require_env(name: str) -> str:
    """Get a required environment variable or exit with an error."""
    value = os.environ.get(name, "")
    if not value:
        logger.error("Required environment variable %s is not set", name)
        sys.exit(1)
    return value


def validate_env_vars(required: List[str]) -> None:
    """Validate that all required environment variables are set.

    Call at startup to fail fast if configuration is missing.
    """
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        logger.error("Missing required environment variables: %s", ", ".join(missing))
        sys.exit(1)
