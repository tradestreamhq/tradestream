-- Correlation analysis tables: daily returns, snapshots, and regime change alerts.

-- Strategy daily returns for correlation computation
CREATE TABLE IF NOT EXISTS strategy_daily_returns (
    id            BIGSERIAL PRIMARY KEY,
    strategy_id   TEXT        NOT NULL,
    metric_date   DATE        NOT NULL,
    daily_return  DOUBLE PRECISION NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (strategy_id, metric_date)
);

CREATE INDEX idx_strategy_daily_returns_lookup
    ON strategy_daily_returns (strategy_id, metric_date);

-- Asset daily returns for cross-asset correlation
CREATE TABLE IF NOT EXISTS asset_daily_returns (
    id            BIGSERIAL PRIMARY KEY,
    symbol        TEXT        NOT NULL,
    metric_date   DATE        NOT NULL,
    daily_return  DOUBLE PRECISION NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (symbol, metric_date)
);

CREATE INDEX idx_asset_daily_returns_lookup
    ON asset_daily_returns (symbol, metric_date);

-- Historical correlation snapshots
CREATE TABLE IF NOT EXISTS correlation_snapshots (
    id               BIGSERIAL PRIMARY KEY,
    correlation_type TEXT        NOT NULL,  -- 'strategy' or 'asset'
    window_days      INT         NOT NULL,
    matrix_json      TEXT        NOT NULL,
    computed_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_correlation_snapshots_lookup
    ON correlation_snapshots (correlation_type, window_days, computed_at DESC);

-- Regime change alerts
CREATE TABLE IF NOT EXISTS correlation_regime_alerts (
    id                    BIGSERIAL PRIMARY KEY,
    correlation_type      TEXT             NOT NULL,
    pair_a                TEXT             NOT NULL,
    pair_b                TEXT             NOT NULL,
    previous_correlation  DOUBLE PRECISION NOT NULL,
    current_correlation   DOUBLE PRECISION NOT NULL,
    absolute_change       DOUBLE PRECISION NOT NULL,
    detected_at           TIMESTAMPTZ      NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_correlation_regime_alerts_time
    ON correlation_regime_alerts (detected_at DESC);
