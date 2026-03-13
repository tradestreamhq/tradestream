-- Paper trading sessions table for managing simulation sessions
-- with configurable starting balance and session lifecycle.
CREATE TABLE paper_trading_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    starting_balance DECIMAL(20, 8) NOT NULL DEFAULT 100000.0,
    current_balance DECIMAL(20, 8) NOT NULL DEFAULT 100000.0,
    status VARCHAR(10) NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'STOPPED')),
    started_at TIMESTAMP NOT NULL DEFAULT NOW(),
    stopped_at TIMESTAMP,
    total_realized_pnl DECIMAL(20, 8) NOT NULL DEFAULT 0,
    total_trades INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX idx_paper_trading_sessions_status ON paper_trading_sessions(status);
CREATE INDEX idx_paper_trading_sessions_started_at ON paper_trading_sessions(started_at DESC);

-- Add session_id to paper_trades to associate trades with sessions.
ALTER TABLE paper_trades ADD COLUMN session_id UUID REFERENCES paper_trading_sessions(id);
CREATE INDEX idx_paper_trades_session_id ON paper_trades(session_id);
