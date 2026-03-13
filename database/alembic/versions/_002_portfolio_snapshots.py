"""Add portfolio_snapshots table for daily equity curve tracking.

Revision ID: 002
Revises: 001
Create Date: 2026-03-13

"""

from typing import Sequence, Union

from alembic import op

revision: str = "002"
down_revision: str = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UPGRADE_SQL = """
-- =============================================================
-- V10: Portfolio snapshots for equity curve
-- =============================================================
CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    snapshot_date DATE NOT NULL,
    total_equity DECIMAL(20, 8) NOT NULL DEFAULT 0,
    total_unrealized_pnl DECIMAL(20, 8) NOT NULL DEFAULT 0,
    total_realized_pnl DECIMAL(20, 8) NOT NULL DEFAULT 0,
    position_count INTEGER NOT NULL DEFAULT 0,
    positions JSONB NOT NULL DEFAULT '[]',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(snapshot_date)
);

CREATE INDEX IF NOT EXISTS idx_portfolio_snapshots_date
    ON portfolio_snapshots(snapshot_date DESC);

-- Add side column to paper_portfolio to support short positions
ALTER TABLE paper_portfolio ADD COLUMN IF NOT EXISTS side VARCHAR(10)
    NOT NULL DEFAULT 'LONG' CHECK (side IN ('LONG', 'SHORT'));
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(
        """
    ALTER TABLE paper_portfolio DROP COLUMN IF EXISTS side;
    DROP TABLE IF EXISTS portfolio_snapshots CASCADE;
    """
    )
