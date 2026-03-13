"""Add optimization_jobs table for strategy parameter optimization.

Revision ID: 002
Revises: 001
Create Date: 2026-03-13

"""

from typing import Sequence, Union

from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UPGRADE_SQL = """
CREATE TABLE IF NOT EXISTS optimization_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_id VARCHAR NOT NULL,
    status VARCHAR NOT NULL DEFAULT 'PENDING',
    search_method VARCHAR NOT NULL DEFAULT 'grid',
    objective VARCHAR NOT NULL DEFAULT 'sharpe',
    total_combinations INTEGER NOT NULL DEFAULT 0,
    completed_combinations INTEGER NOT NULL DEFAULT 0,
    best_parameters JSONB,
    best_objective_value DOUBLE PRECISION,
    ranked_results JSONB,
    error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_optimization_jobs_strategy_id
    ON optimization_jobs (strategy_id);
CREATE INDEX IF NOT EXISTS idx_optimization_jobs_status
    ON optimization_jobs (status);
CREATE INDEX IF NOT EXISTS idx_optimization_jobs_created_at
    ON optimization_jobs (created_at DESC);
"""

DOWNGRADE_SQL = """
DROP TABLE IF EXISTS optimization_jobs;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
