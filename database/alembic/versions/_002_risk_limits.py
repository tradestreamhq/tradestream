"""Add risk_limits table for user-configured risk management.

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
-- =============================================================
-- V10: Risk limits
-- =============================================================
CREATE TABLE IF NOT EXISTS risk_limits (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    max_position_size DECIMAL(20, 8) NOT NULL DEFAULT 10000,
    max_position_pct DECIMAL(5, 4) NOT NULL DEFAULT 0.05,
    max_daily_loss DECIMAL(20, 8) NOT NULL DEFAULT 1000,
    max_daily_loss_pct DECIMAL(5, 4) NOT NULL DEFAULT 0.02,
    max_drawdown_pct DECIMAL(5, 4) NOT NULL DEFAULT 0.10,
    max_open_positions INTEGER NOT NULL DEFAULT 20,
    max_sector_exposure_pct DECIMAL(5, 4) NOT NULL DEFAULT 0.30,
    max_correlated_exposure_pct DECIMAL(5, 4) NOT NULL DEFAULT 0.40,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_risk_limits_updated_at ON risk_limits(updated_at);

DROP TRIGGER IF EXISTS update_risk_limits_updated_at ON risk_limits;
CREATE TRIGGER update_risk_limits_updated_at
    BEFORE UPDATE ON risk_limits
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Insert default risk limits row
INSERT INTO risk_limits (
    max_position_size, max_position_pct, max_daily_loss,
    max_daily_loss_pct, max_drawdown_pct, max_open_positions,
    max_sector_exposure_pct, max_correlated_exposure_pct
) VALUES (
    10000, 0.05, 1000, 0.02, 0.10, 20, 0.30, 0.40
);
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS risk_limits CASCADE;")
