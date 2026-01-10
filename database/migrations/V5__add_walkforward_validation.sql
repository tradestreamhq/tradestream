-- V5__add_walkforward_validation.sql
-- Add walk-forward validation metrics for detecting overfitting
-- These metrics track out-of-sample performance from walk-forward optimization

-- Add walk-forward validation columns to Strategies table
ALTER TABLE Strategies ADD COLUMN IF NOT EXISTS oos_sharpe DOUBLE PRECISION;
ALTER TABLE Strategies ADD COLUMN IF NOT EXISTS oos_return DOUBLE PRECISION;
ALTER TABLE Strategies ADD COLUMN IF NOT EXISTS sharpe_degradation DOUBLE PRECISION;
ALTER TABLE Strategies ADD COLUMN IF NOT EXISTS oos_sharpe_std_dev DOUBLE PRECISION;
ALTER TABLE Strategies ADD COLUMN IF NOT EXISTS validation_status VARCHAR(20);
ALTER TABLE Strategies ADD COLUMN IF NOT EXISTS wf_windows_count INTEGER;
ALTER TABLE Strategies ADD COLUMN IF NOT EXISTS validation_rejection_reason TEXT;
ALTER TABLE Strategies ADD COLUMN IF NOT EXISTS validated_at TIMESTAMP;

-- Comments for documentation
COMMENT ON COLUMN Strategies.oos_sharpe IS 'Mean out-of-sample Sharpe ratio from walk-forward validation';
COMMENT ON COLUMN Strategies.oos_return IS 'Mean out-of-sample return from walk-forward validation';
COMMENT ON COLUMN Strategies.sharpe_degradation IS 'Sharpe degradation: 1 - (OOS Sharpe / IS Sharpe). Lower is better.';
COMMENT ON COLUMN Strategies.oos_sharpe_std_dev IS 'Standard deviation of OOS Sharpe across windows (consistency metric)';
COMMENT ON COLUMN Strategies.validation_status IS 'Walk-forward validation status: APPROVED, REJECTED, INSUFFICIENT_DATA, PENDING';
COMMENT ON COLUMN Strategies.wf_windows_count IS 'Number of walk-forward windows used for validation';
COMMENT ON COLUMN Strategies.validation_rejection_reason IS 'Reason for rejection if validation_status is REJECTED';
COMMENT ON COLUMN Strategies.validated_at IS 'Timestamp when walk-forward validation was last run';

-- Index for finding validated strategies efficiently
CREATE INDEX IF NOT EXISTS idx_strategies_validation_status
ON Strategies(validation_status);

-- Index for finding approved strategies sorted by OOS performance
CREATE INDEX IF NOT EXISTS idx_strategies_validated_approved
ON Strategies(validation_status, oos_sharpe DESC)
WHERE validation_status = 'APPROVED';

-- Walk-forward validation results table - detailed per-window results
CREATE TABLE IF NOT EXISTS walk_forward_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_id UUID NOT NULL REFERENCES Strategies(strategy_id) ON DELETE CASCADE,

    -- Aggregated metrics (same as stored on Strategies, but historical record)
    in_sample_sharpe DOUBLE PRECISION NOT NULL,
    out_of_sample_sharpe DOUBLE PRECISION NOT NULL,
    sharpe_degradation DOUBLE PRECISION NOT NULL,
    oos_sharpe_std_dev DOUBLE PRECISION,

    in_sample_return DOUBLE PRECISION,
    out_of_sample_return DOUBLE PRECISION,
    return_degradation DOUBLE PRECISION,

    -- Configuration used
    train_window_bars INTEGER NOT NULL,
    test_window_bars INTEGER NOT NULL,
    step_bars INTEGER NOT NULL,
    windows_count INTEGER NOT NULL,

    -- Validation decision
    validation_status VARCHAR(20) NOT NULL,
    rejection_reason TEXT,

    -- Full window results as JSONB for detailed analysis
    window_results JSONB,

    -- Metadata
    validated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Indexes for walk_forward_results
CREATE INDEX IF NOT EXISTS idx_wf_strategy_id ON walk_forward_results(strategy_id);
CREATE INDEX IF NOT EXISTS idx_wf_validated_at ON walk_forward_results(validated_at);
CREATE INDEX IF NOT EXISTS idx_wf_status ON walk_forward_results(validation_status);

-- Comments
COMMENT ON TABLE walk_forward_results IS 'Historical walk-forward validation results. Stores full validation details for analysis and debugging.';
