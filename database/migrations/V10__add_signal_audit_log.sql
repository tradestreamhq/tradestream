-- V10__add_signal_audit_log.sql
-- Add signal_audit_log table for recording all signal events with full context.
-- Supports signal replay and debugging via append-only event log.

CREATE TABLE IF NOT EXISTS signal_audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sequence_number BIGINT NOT NULL GENERATED ALWAYS AS IDENTITY,

    -- Event identification
    event_type VARCHAR(50) NOT NULL,  -- 'SIGNAL_EMITTED', 'SIGNAL_SKIPPED', 'DECISION_LOGGED', 'REPLAY_STARTED', 'REPLAY_COMPLETED'
    signal_id UUID REFERENCES signals(id) ON DELETE SET NULL,

    -- Signal snapshot at event time
    symbol VARCHAR(50) NOT NULL,
    action VARCHAR(20),               -- 'BUY', 'SELL', 'HOLD'
    confidence DECIMAL(5,4),
    reasoning TEXT,
    strategy_breakdown JSONB,

    -- Market state snapshot
    market_state JSONB,               -- Price, volume, volatility at event time

    -- Agent context
    model_used VARCHAR(100),
    tool_calls JSONB,                 -- Ordered list of tool calls leading to this event
    agent_parameters JSONB,           -- Any agent configuration at event time

    -- Replay support
    replay_group_id UUID,             -- Groups events from a single replay session
    is_replay BOOLEAN NOT NULL DEFAULT FALSE,

    -- Original event reference (for replay comparison)
    original_event_id UUID REFERENCES signal_audit_log(id) ON DELETE SET NULL,

    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_signal_audit_log_sequence ON signal_audit_log(sequence_number);
CREATE INDEX IF NOT EXISTS idx_signal_audit_log_symbol_time ON signal_audit_log(symbol, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_signal_audit_log_event_type ON signal_audit_log(event_type);
CREATE INDEX IF NOT EXISTS idx_signal_audit_log_signal_id ON signal_audit_log(signal_id);
CREATE INDEX IF NOT EXISTS idx_signal_audit_log_replay_group ON signal_audit_log(replay_group_id) WHERE replay_group_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_signal_audit_log_created_at ON signal_audit_log(created_at DESC);

COMMENT ON TABLE signal_audit_log IS 'Append-only audit log for all signal events. Supports replay and debugging.';
