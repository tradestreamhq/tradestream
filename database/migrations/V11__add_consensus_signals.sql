-- Consensus signals table for storing aggregated signal consensus
CREATE TABLE IF NOT EXISTS consensus_signals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    instrument TEXT NOT NULL,
    direction TEXT NOT NULL CHECK (direction IN ('LONG', 'SHORT', 'NEUTRAL')),
    confidence DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    contributing_signals INTEGER NOT NULL DEFAULT 0,
    agreeing_signals INTEGER NOT NULL DEFAULT 0,
    dissenting_signals INTEGER NOT NULL DEFAULT 0,
    weighted_score DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    avg_price DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    signal_details JSONB DEFAULT '[]'::jsonb,
    window_start TIMESTAMPTZ,
    window_end TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_consensus_signals_instrument ON consensus_signals(instrument);
CREATE INDEX idx_consensus_signals_instrument_time ON consensus_signals(instrument, created_at DESC);
CREATE INDEX idx_consensus_signals_created_at ON consensus_signals(created_at DESC);
