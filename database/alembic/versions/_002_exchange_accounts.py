"""Add exchange_accounts table for multi-exchange account management.

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
CREATE TABLE IF NOT EXISTS exchange_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    exchange VARCHAR(50) NOT NULL,
    label VARCHAR(255) NOT NULL,
    encrypted_api_key TEXT NOT NULL,
    encrypted_api_secret TEXT NOT NULL,
    permissions JSONB NOT NULL DEFAULT '["read"]',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_exchange_accounts_exchange
    ON exchange_accounts(exchange);
CREATE INDEX IF NOT EXISTS idx_exchange_accounts_is_active
    ON exchange_accounts(is_active);
CREATE UNIQUE INDEX IF NOT EXISTS idx_exchange_accounts_label_exchange
    ON exchange_accounts(label, exchange) WHERE is_active = TRUE;

DROP TRIGGER IF EXISTS update_exchange_accounts_updated_at ON exchange_accounts;
CREATE TRIGGER update_exchange_accounts_updated_at
    BEFORE UPDATE ON exchange_accounts
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS exchange_accounts CASCADE;")
