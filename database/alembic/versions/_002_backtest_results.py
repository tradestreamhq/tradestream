"""Add backtest_results table for storing historical backtest runs.

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
CREATE TABLE IF NOT EXISTS backtest_results (
    backtest_id VARCHAR(36) PRIMARY KEY,
    strategy_name VARCHAR(255) NOT NULL,
    config JSONB NOT NULL DEFAULT '{}',
    start_date VARCHAR(64),
    end_date VARCHAR(64),
    initial_capital DOUBLE PRECISION NOT NULL,
    final_capital DOUBLE PRECISION NOT NULL,
    total_return DOUBLE PRECISION NOT NULL,
    annualized_return DOUBLE PRECISION NOT NULL,
    sharpe_ratio DOUBLE PRECISION NOT NULL DEFAULT 0,
    sortino_ratio DOUBLE PRECISION NOT NULL DEFAULT 0,
    max_drawdown DOUBLE PRECISION NOT NULL DEFAULT 0,
    max_drawdown_duration_bars INTEGER NOT NULL DEFAULT 0,
    number_of_trades INTEGER NOT NULL DEFAULT 0,
    win_rate DOUBLE PRECISION NOT NULL DEFAULT 0,
    profit_factor DOUBLE PRECISION NOT NULL DEFAULT 0,
    avg_holding_period_bars DOUBLE PRECISION NOT NULL DEFAULT 0,
    avg_win DOUBLE PRECISION NOT NULL DEFAULT 0,
    avg_loss DOUBLE PRECISION NOT NULL DEFAULT 0,
    total_commission DOUBLE PRECISION NOT NULL DEFAULT 0,
    trades JSONB NOT NULL DEFAULT '[]',
    created_at VARCHAR(64) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_backtest_results_strategy_name
    ON backtest_results(strategy_name);
CREATE INDEX IF NOT EXISTS idx_backtest_results_sharpe_ratio
    ON backtest_results(sharpe_ratio);
CREATE INDEX IF NOT EXISTS idx_backtest_results_created_at
    ON backtest_results(created_at);
CREATE INDEX IF NOT EXISTS idx_backtest_results_total_return
    ON backtest_results(total_return);
"""

DOWNGRADE_SQL = """
DROP TABLE IF EXISTS backtest_results;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
