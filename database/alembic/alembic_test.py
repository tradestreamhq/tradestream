"""Tests for Alembic migration framework integrity.

Verifies migration chain consistency, import validity, and upgrade/downgrade
operations without requiring a live database.
"""

import importlib
import os
import sys

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory


@pytest.fixture
def alembic_config():
    """Create an Alembic Config pointing to our migration directory."""
    here = os.path.dirname(os.path.abspath(__file__))
    ini_path = os.path.join(here, "alembic.ini")
    config = Config(ini_path)
    config.set_main_option("script_location", here)
    return config


@pytest.fixture
def script_dir(alembic_config):
    """Get the Alembic ScriptDirectory for inspecting migrations."""
    return ScriptDirectory.from_config(alembic_config)


class TestMigrationChain:
    """Tests for migration chain integrity."""

    def test_single_head(self, script_dir):
        """Verify there is exactly one migration head (no branches)."""
        heads = script_dir.get_heads()
        assert len(heads) == 1, (
            f"Expected exactly 1 migration head, found {len(heads)}: {heads}. "
            "Multiple heads indicate a branching conflict."
        )

    def test_head_is_001(self, script_dir):
        """Verify the current head is the baseline migration."""
        heads = script_dir.get_heads()
        assert heads[0] == "001", f"Expected head '001', got '{heads[0]}'"

    def test_linear_chain(self, script_dir):
        """Verify the migration chain is linear (no gaps or cycles)."""
        revisions = list(script_dir.walk_revisions())
        assert len(revisions) > 0, "No migrations found"

        # Walk from head to base should be a clean chain
        for rev in revisions:
            # Each revision should have at most one down_revision
            down = rev.down_revision
            assert down is None or isinstance(down, str), (
                f"Revision {rev.revision} has a non-linear down_revision: {down}. "
                "Use a single parent per migration."
            )

    def test_all_revisions_importable(self, script_dir):
        """Verify all migration modules can be imported without errors."""
        for rev in script_dir.walk_revisions():
            module = rev.module
            assert hasattr(module, "upgrade"), (
                f"Migration {rev.revision} is missing an upgrade() function"
            )
            assert hasattr(module, "downgrade"), (
                f"Migration {rev.revision} is missing a downgrade() function"
            )


class TestBaselineMigration:
    """Tests for the baseline (001) migration content."""

    def test_baseline_contains_all_tables(self, script_dir):
        """Verify the baseline migration creates all expected tables."""
        rev = script_dir.get_revision("001")
        module = rev.module

        # The UPGRADE_SQL should reference all V1-V9 tables
        sql = module.UPGRADE_SQL
        expected_tables = [
            "Strategies",
            "strategy_specs",
            "strategy_implementations",
            "strategy_performance",
            "signals",
            "walk_forward_results",
            "agent_decisions",
            "paper_trades",
            "paper_portfolio",
        ]

        for table in expected_tables:
            assert table in sql, (
                f"Baseline migration is missing table '{table}'. "
                "All tables from V1-V9 should be in the baseline."
            )

    def test_baseline_uses_if_not_exists(self, script_dir):
        """Verify baseline uses IF NOT EXISTS for idempotent application."""
        rev = script_dir.get_revision("001")
        sql = rev.module.UPGRADE_SQL

        # Count CREATE TABLE statements
        create_count = sql.count("CREATE TABLE")
        if_not_exists_count = sql.count("CREATE TABLE IF NOT EXISTS")

        assert create_count == if_not_exists_count, (
            f"Found {create_count} CREATE TABLE statements but only "
            f"{if_not_exists_count} use IF NOT EXISTS. "
            "All table creation must be idempotent."
        )

    def test_downgrade_drops_all_tables(self, script_dir):
        """Verify the downgrade drops all tables created by upgrade."""
        rev = script_dir.get_revision("001")
        module = rev.module

        # Call downgrade indirectly by checking the source
        import inspect
        source = inspect.getsource(module.downgrade)

        expected_drops = [
            "paper_portfolio",
            "paper_trades",
            "agent_decisions",
            "walk_forward_results",
            "signals",
            "strategy_performance",
            "strategy_implementations",
            "strategy_specs",
            "Strategies",
        ]

        for table in expected_drops:
            assert table in source, (
                f"Downgrade is missing DROP for table '{table}'"
            )


class TestRunMigrations:
    """Tests for the migration runner module."""

    def test_run_migrations_importable(self):
        """Verify run_migrations module can be imported."""
        from database.alembic import run_migrations

        assert hasattr(run_migrations, "run_migrations")
        assert hasattr(run_migrations, "get_alembic_config")

    def test_get_alembic_config_returns_valid_config(self):
        """Verify get_alembic_config returns a usable Config object."""
        from database.alembic.run_migrations import get_alembic_config

        config = get_alembic_config()
        assert config is not None
        assert config.get_main_option("script_location") is not None
