"""Add alert_rules and alerts tables.

Revision ID: 002
Revises: 001
Create Date: 2026-03-12
"""

from alembic import op

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS alert_rules (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name VARCHAR(255) NOT NULL,
            strategy_id UUID REFERENCES strategy_specs(id) ON DELETE SET NULL,
            alert_type VARCHAR(50) NOT NULL CHECK (alert_type IN (
                'signal_triggered', 'position_opened', 'position_closed',
                'stop_loss_hit', 'take_profit_hit', 'risk_limit_breached'
            )),
            conditions JSONB NOT NULL DEFAULT '{}'::jsonb,
            enabled BOOLEAN NOT NULL DEFAULT true,
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        );

        CREATE INDEX IF NOT EXISTS idx_alert_rules_strategy_id
            ON alert_rules(strategy_id);
        CREATE INDEX IF NOT EXISTS idx_alert_rules_alert_type
            ON alert_rules(alert_type);
        CREATE INDEX IF NOT EXISTS idx_alert_rules_enabled
            ON alert_rules(enabled);

        CREATE TABLE IF NOT EXISTS alerts (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            rule_id UUID REFERENCES alert_rules(id) ON DELETE SET NULL,
            strategy_id UUID REFERENCES strategy_specs(id) ON DELETE SET NULL,
            alert_type VARCHAR(50) NOT NULL CHECK (alert_type IN (
                'signal_triggered', 'position_opened', 'position_closed',
                'stop_loss_hit', 'take_profit_hit', 'risk_limit_breached'
            )),
            status VARCHAR(20) NOT NULL DEFAULT 'created' CHECK (status IN (
                'created', 'sent', 'acknowledged', 'dismissed'
            )),
            message TEXT,
            details JSONB DEFAULT '{}'::jsonb,
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        );

        CREATE INDEX IF NOT EXISTS idx_alerts_rule_id ON alerts(rule_id);
        CREATE INDEX IF NOT EXISTS idx_alerts_strategy_id ON alerts(strategy_id);
        CREATE INDEX IF NOT EXISTS idx_alerts_alert_type ON alerts(alert_type);
        CREATE INDEX IF NOT EXISTS idx_alerts_status ON alerts(status);
        CREATE INDEX IF NOT EXISTS idx_alerts_created_at ON alerts(created_at DESC);
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS alerts;")
    op.execute("DROP TABLE IF EXISTS alert_rules;")
