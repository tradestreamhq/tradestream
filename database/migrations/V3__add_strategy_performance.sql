-- V3__add_strategy_performance.sql
-- Add strategy performance tracking tables
-- Enables historical performance analysis and learning

-- Strategy performance history - detailed performance records
CREATE TABLE IF NOT EXISTS strategy_performance (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    implementation_id UUID NOT NULL REFERENCES strategy_implementations(id) ON DELETE CASCADE,

    -- Time period
    period_start TIMESTAMP NOT NULL,
    period_end TIMESTAMP NOT NULL,

    -- Core metrics
    sharpe_ratio DECIMAL(10,4),
    sortino_ratio DECIMAL(10,4),
    calmar_ratio DECIMAL(10,4),
    win_rate DECIMAL(5,4),
    profit_factor DECIMAL(10,4),

    -- Risk metrics
    max_drawdown DECIMAL(10,4),
    avg_drawdown DECIMAL(10,4),
    volatility DECIMAL(10,4),
    var_95 DECIMAL(10,4),  -- Value at Risk 95%

    -- Trade statistics
    total_trades INTEGER NOT NULL DEFAULT 0,
    winning_trades INTEGER NOT NULL DEFAULT 0,
    losing_trades INTEGER NOT NULL DEFAULT 0,
    avg_trade_duration_seconds BIGINT,
    avg_profit_per_trade DECIMAL(20,8),

    -- Returns
    total_return DECIMAL(10,4),
    annualized_return DECIMAL(10,4),

    -- Environment
    environment VARCHAR(20) NOT NULL, -- 'BACKTEST', 'PAPER', 'LIVE'
    instrument VARCHAR(50) NOT NULL,
    timeframe VARCHAR(20),            -- '1m', '5m', '1h', '1d', etc.

    -- Metadata
    raw_metrics JSONB,                -- Full metrics dump for analysis
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Indexes for strategy_performance
CREATE INDEX IF NOT EXISTS idx_perf_impl_id ON strategy_performance(implementation_id);
CREATE INDEX IF NOT EXISTS idx_perf_impl_date ON strategy_performance(implementation_id, period_start);
CREATE INDEX IF NOT EXISTS idx_perf_environment ON strategy_performance(environment);
CREATE INDEX IF NOT EXISTS idx_perf_instrument ON strategy_performance(instrument);
CREATE INDEX IF NOT EXISTS idx_perf_created_at ON strategy_performance(created_at);

-- Partition hint for future: consider partitioning by period_start for large datasets
COMMENT ON TABLE strategy_performance IS 'Historical performance records for strategy implementations. Consider partitioning by period_start for datasets > 10M rows.';
