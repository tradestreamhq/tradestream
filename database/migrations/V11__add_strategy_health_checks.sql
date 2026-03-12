-- Strategy health monitoring: tracks heartbeats, uptime, and operational metrics per strategy.

CREATE TABLE strategy_health_checks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_id     UUID NOT NULL,
    status          VARCHAR(20) NOT NULL DEFAULT 'offline',
    last_heartbeat  TIMESTAMP WITH TIME ZONE,
    uptime_pct      DECIMAL(5, 2) DEFAULT 0.00,
    error_count     INTEGER NOT NULL DEFAULT 0,
    warning_count   INTEGER NOT NULL DEFAULT 0,
    last_error_msg  TEXT,
    metadata        JSONB DEFAULT '{}'::jsonb,
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_strategy_health_strategy
        FOREIGN KEY (strategy_id) REFERENCES strategy_implementations(id)
        ON DELETE CASCADE,

    CONSTRAINT chk_status
        CHECK (status IN ('healthy', 'degraded', 'unhealthy', 'offline'))
);

CREATE UNIQUE INDEX idx_strategy_health_strategy_id ON strategy_health_checks(strategy_id);
CREATE INDEX idx_strategy_health_status ON strategy_health_checks(status);

-- History table for health status timeline
CREATE TABLE strategy_health_history (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_id     UUID NOT NULL,
    status          VARCHAR(20) NOT NULL,
    error_count     INTEGER NOT NULL DEFAULT 0,
    warning_count   INTEGER NOT NULL DEFAULT 0,
    last_error_msg  TEXT,
    recorded_at     TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_health_history_strategy
        FOREIGN KEY (strategy_id) REFERENCES strategy_implementations(id)
        ON DELETE CASCADE
);

CREATE INDEX idx_health_history_strategy_time
    ON strategy_health_history(strategy_id, recorded_at DESC);

-- Auto-update updated_at
CREATE TRIGGER update_strategy_health_checks_updated_at
    BEFORE UPDATE ON strategy_health_checks
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
