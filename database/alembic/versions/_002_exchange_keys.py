"""Add exchange_keys table for multi-exchange API key management.

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
CREATE TABLE IF NOT EXISTS exchange_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    exchange_name VARCHAR(50) NOT NULL,
    api_key_encrypted TEXT NOT NULL,
    api_secret_encrypted TEXT NOT NULL,
    label VARCHAR(255),
    permissions TEXT[] NOT NULL DEFAULT '{read}',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    last_used_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_exchange_keys_exchange_name ON exchange_keys(exchange_name);
CREATE INDEX IF NOT EXISTS idx_exchange_keys_is_active ON exchange_keys(is_active);
CREATE INDEX IF NOT EXISTS idx_exchange_keys_created_at ON exchange_keys(created_at DESC);

DROP TRIGGER IF EXISTS update_exchange_keys_updated_at ON exchange_keys;
CREATE TRIGGER update_exchange_keys_updated_at
    BEFORE UPDATE ON exchange_keys
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS exchange_keys CASCADE;")
