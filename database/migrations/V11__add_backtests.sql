-- Backtest results storage
CREATE TABLE IF NOT EXISTS backtests (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_id     TEXT NOT NULL,
    symbol          TEXT NOT NULL,
    timeframe       TEXT NOT NULL,
    start_date      TIMESTAMPTZ NOT NULL,
    end_date        TIMESTAMPTZ NOT NULL,
    status          TEXT NOT NULL DEFAULT 'PENDING',
    total_return    DOUBLE PRECISION,
    sharpe_ratio    DOUBLE PRECISION,
    max_drawdown    DOUBLE PRECISION,
    win_rate        DOUBLE PRECISION,
    profit_factor   DOUBLE PRECISION,
    total_trades    INTEGER,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at    TIMESTAMPTZ
);

CREATE INDEX idx_backtests_strategy_id ON backtests (strategy_id);
CREATE INDEX idx_backtests_symbol ON backtests (symbol);
CREATE INDEX idx_backtests_status ON backtests (status);
CREATE INDEX idx_backtests_created_at ON backtests (created_at DESC);

-- Equity curve data points for each backtest
CREATE TABLE IF NOT EXISTS backtest_equity_curve (
    id              BIGSERIAL PRIMARY KEY,
    backtest_id     UUID NOT NULL REFERENCES backtests(id) ON DELETE CASCADE,
    timestamp       TIMESTAMPTZ NOT NULL,
    equity          DOUBLE PRECISION NOT NULL,
    drawdown        DOUBLE PRECISION NOT NULL DEFAULT 0
);

CREATE INDEX idx_equity_curve_backtest ON backtest_equity_curve (backtest_id, timestamp);

-- Simulated trades produced by the backtest
CREATE TABLE IF NOT EXISTS backtest_trades (
    id              BIGSERIAL PRIMARY KEY,
    backtest_id     UUID NOT NULL REFERENCES backtests(id) ON DELETE CASCADE,
    side            TEXT NOT NULL,
    entry_time      TIMESTAMPTZ NOT NULL,
    exit_time       TIMESTAMPTZ,
    entry_price     DOUBLE PRECISION NOT NULL,
    exit_price      DOUBLE PRECISION,
    quantity        DOUBLE PRECISION NOT NULL DEFAULT 1.0,
    pnl             DOUBLE PRECISION
);

CREATE INDEX idx_backtest_trades_backtest ON backtest_trades (backtest_id);
