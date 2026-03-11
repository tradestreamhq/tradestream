"""
Standalone migration runner for TradeStream database.

Usage:
    python -m database.alembic.run_migrations [--stamp-only]

Environment variables:
    POSTGRES_HOST     (default: localhost)
    POSTGRES_PORT     (default: 5432)
    POSTGRES_DB       (default: tradestream)
    POSTGRES_USER     (default: postgres)
    POSTGRES_PASSWORD (required)
"""

import argparse
import os
import sys

from alembic import command
from alembic.config import Config


def get_alembic_config():
    """Create Alembic config pointing to our migrations."""
    # Resolve path relative to this file
    here = os.path.dirname(os.path.abspath(__file__))
    ini_path = os.path.join(here, "alembic.ini")

    config = Config(ini_path)
    config.set_main_option("script_location", here)
    return config


def run_migrations(stamp_only=False):
    """Run pending migrations or stamp current revision."""
    config = get_alembic_config()

    if stamp_only:
        # Mark current revision without running migrations.
        # Use this on existing databases that already have the schema from Flyway.
        command.stamp(config, "head")
        print("Stamped database at head revision (no migrations executed).")
    else:
        command.upgrade(config, "head")
        print("Migrations applied successfully.")


def main():
    parser = argparse.ArgumentParser(description="Run TradeStream database migrations")
    parser.add_argument(
        "--stamp-only",
        action="store_true",
        help="Stamp the database at head without running migrations "
        "(use for existing databases already managed by Flyway)",
    )
    args = parser.parse_args()

    if not os.environ.get("POSTGRES_PASSWORD"):
        print(
            "Error: POSTGRES_PASSWORD environment variable is required", file=sys.stderr
        )
        sys.exit(1)

    run_migrations(stamp_only=args.stamp_only)


if __name__ == "__main__":
    main()
