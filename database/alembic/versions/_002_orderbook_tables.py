"""Add order book snapshot and history tables.

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
-- Order book snapshots (latest state per symbol/exchange)
-- =============================================================
CREATE TABLE IF NOT EXISTS orderbook_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol VARCHAR NOT NULL,
    exchange VARCHAR NOT NULL,
    bids JSONB NOT NULL DEFAULT '[]',
    asks JSONB NOT NULL DEFAULT '[]',
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    sequence_number BIGINT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_orderbook_snapshots_symbol
    ON orderbook_snapshots(symbol);
CREATE INDEX IF NOT EXISTS idx_orderbook_snapshots_symbol_exchange
    ON orderbook_snapshots(symbol, exchange);
CREATE INDEX IF NOT EXISTS idx_orderbook_snapshots_timestamp
    ON orderbook_snapshots(timestamp DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_orderbook_snapshots_symbol_exchange_seq
    ON orderbook_snapshots(symbol, exchange, sequence_number);

-- =============================================================
-- Order book history (periodic spread/imbalance for time series)
-- =============================================================
CREATE TABLE IF NOT EXISTS orderbook_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol VARCHAR NOT NULL,
    exchange VARCHAR NOT NULL,
    best_bid DOUBLE PRECISION,
    best_ask DOUBLE PRECISION,
    spread DOUBLE PRECISION,
    mid_price DOUBLE PRECISION,
    spread_percentage DOUBLE PRECISION,
    imbalance DOUBLE PRECISION,
    bid_volume DOUBLE PRECISION,
    ask_volume DOUBLE PRECISION,
    depth INT NOT NULL DEFAULT 10,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_orderbook_history_symbol
    ON orderbook_history(symbol);
CREATE INDEX IF NOT EXISTS idx_orderbook_history_symbol_exchange
    ON orderbook_history(symbol, exchange);
CREATE INDEX IF NOT EXISTS idx_orderbook_history_timestamp
    ON orderbook_history(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_orderbook_history_symbol_timestamp
    ON orderbook_history(symbol, timestamp DESC);
"""

DOWNGRADE_SQL = """
DROP TABLE IF EXISTS orderbook_history CASCADE;
DROP TABLE IF EXISTS orderbook_snapshots CASCADE;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
