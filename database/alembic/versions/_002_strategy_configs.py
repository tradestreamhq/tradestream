"""Add strategy_configs table for version-controlled strategy parameters.

Revision ID: 002
Revises: 001
Create Date: 2026-03-12

"""

from typing import Sequence, Union

from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UPGRADE_SQL = """
-- =============================================================
-- Strategy configuration versioning
-- =============================================================
CREATE TABLE IF NOT EXISTS strategy_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_id UUID NOT NULL REFERENCES strategy_specs(id) ON DELETE CASCADE,
    version INTEGER NOT NULL DEFAULT 1,
    parameters JSONB NOT NULL,
    description TEXT,
    author VARCHAR(255),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Only one active config per strategy
CREATE UNIQUE INDEX IF NOT EXISTS idx_strategy_configs_active
    ON strategy_configs (strategy_id) WHERE is_active = TRUE;

CREATE INDEX IF NOT EXISTS idx_strategy_configs_strategy_id
    ON strategy_configs(strategy_id);

CREATE INDEX IF NOT EXISTS idx_strategy_configs_version
    ON strategy_configs(strategy_id, version DESC);

CREATE INDEX IF NOT EXISTS idx_strategy_configs_created_at
    ON strategy_configs(created_at DESC);
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS strategy_configs CASCADE;")
