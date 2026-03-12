"""Webhook management tables.

Revision ID: 002
Revises: 001
Create Date: 2026-03-12
"""

from typing import Union

from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels = None
depends_on = None

UPGRADE_SQL = """
CREATE TABLE IF NOT EXISTS webhooks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    url TEXT NOT NULL,
    secret TEXT NOT NULL DEFAULT '',
    event_types TEXT[] NOT NULL DEFAULT '{}',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    retry_policy JSONB NOT NULL DEFAULT '{"max_retries": 3, "backoff_seconds": [1, 5, 30]}',
    description TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_webhooks_is_active ON webhooks(is_active);

CREATE TABLE IF NOT EXISTS webhook_deliveries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    webhook_id UUID NOT NULL REFERENCES webhooks(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    payload JSONB NOT NULL,
    status_code INT,
    response_body TEXT,
    response_time_ms INT,
    attempt INT NOT NULL DEFAULT 1,
    success BOOLEAN NOT NULL DEFAULT FALSE,
    error TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_webhook_deliveries_webhook_id
    ON webhook_deliveries(webhook_id, created_at DESC);
"""

DOWNGRADE_SQL = """
DROP TABLE IF EXISTS webhook_deliveries;
DROP TABLE IF EXISTS webhooks;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
