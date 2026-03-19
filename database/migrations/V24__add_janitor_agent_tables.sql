-- Janitor Agent tables: retirement log, reactivation log, reports, and regime detection

-- Retirement log for auditing
CREATE TABLE IF NOT EXISTS retirement_log (
    log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    impl_id UUID REFERENCES strategy_implementations(impl_id),
    spec_id UUID REFERENCES strategy_specs(spec_id),
    retirement_type VARCHAR(20) NOT NULL,
    reason TEXT NOT NULL,
    agent_reasoning TEXT,
    retired_at TIMESTAMP DEFAULT NOW(),
    can_reactivate BOOLEAN DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_retirement_log_impl ON retirement_log(impl_id);
CREATE INDEX IF NOT EXISTS idx_retirement_log_spec ON retirement_log(spec_id);
CREATE INDEX IF NOT EXISTS idx_retirement_log_date ON retirement_log(retired_at DESC);

-- Reactivation log for tracking
CREATE TABLE IF NOT EXISTS reactivation_log (
    log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    impl_id UUID REFERENCES strategy_implementations(impl_id),
    reason TEXT NOT NULL,
    requester VARCHAR(100) NOT NULL,
    reactivated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_reactivation_log_impl ON reactivation_log(impl_id);

-- Janitor reports for historical analysis
CREATE TABLE IF NOT EXISTS janitor_reports (
    report_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    report_date DATE NOT NULL UNIQUE,
    evaluated_count INTEGER NOT NULL,
    retired_implementations INTEGER NOT NULL,
    retired_specs INTEGER NOT NULL,
    protected_count INTEGER NOT NULL,
    report_markdown TEXT NOT NULL,
    storage_path VARCHAR(500),
    distributed_to JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_janitor_reports_date ON janitor_reports(report_date DESC);

-- Sharpe trend calculation function
CREATE OR REPLACE FUNCTION calculate_sharpe_trend(
    p_impl_id UUID,
    p_lookback_months INTEGER DEFAULT 6
)
RETURNS VARCHAR(20) AS $$
DECLARE
    trend_slope DECIMAL;
    month_count INTEGER;
BEGIN
    SELECT
        regr_slope(sharpe, month_num),
        COUNT(DISTINCT month_num)
    INTO trend_slope, month_count
    FROM (
        SELECT
            EXTRACT(MONTH FROM signal_timestamp) +
            EXTRACT(YEAR FROM signal_timestamp) * 12 as month_num,
            AVG(return_pct) / NULLIF(STDDEV(return_pct), 0) as sharpe
        FROM implementation_signals
        WHERE impl_id = p_impl_id
          AND signal_type = 'forward_test'
          AND signal_timestamp > NOW() - INTERVAL '1 month' * p_lookback_months
        GROUP BY 1
        ORDER BY 1
    ) monthly_sharpe;

    IF month_count < 3 THEN
        RETURN 'INSUFFICIENT_DATA';
    END IF;

    IF trend_slope IS NULL THEN
        RETURN 'INSUFFICIENT_DATA';
    ELSIF trend_slope < -0.02 THEN
        RETURN 'DECLINING';
    ELSIF trend_slope > 0.02 THEN
        RETURN 'IMPROVING';
    ELSE
        RETURN 'STABLE';
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Market regime detection function
CREATE OR REPLACE FUNCTION detect_market_regime(
    p_symbol VARCHAR(20),
    p_lookback_days INTEGER DEFAULT 30
)
RETURNS VARCHAR(20) AS $$
DECLARE
    volatility_ratio DECIMAL;
    trend_strength DECIMAL;
BEGIN
    SELECT
        AVG(CASE WHEN rn <= 5 THEN atr END) / NULLIF(AVG(atr), 0),
        REGR_SLOPE(close_price, row_num)
    INTO volatility_ratio, trend_strength
    FROM (
        SELECT
            atr,
            close_price,
            ROW_NUMBER() OVER (ORDER BY timestamp DESC) as rn,
            ROW_NUMBER() OVER (ORDER BY timestamp ASC) as row_num
        FROM market_data
        WHERE symbol = p_symbol
          AND timestamp > NOW() - INTERVAL '1 day' * p_lookback_days
    ) data;

    IF volatility_ratio IS NULL OR trend_strength IS NULL THEN
        RETURN 'ranging';
    END IF;

    IF volatility_ratio > 1.5 THEN
        RETURN 'high_vol';
    ELSIF volatility_ratio < 0.5 THEN
        RETURN 'low_vol';
    ELSIF ABS(trend_strength) > 0.02 THEN
        IF trend_strength > 0 THEN
            RETURN 'trending_up';
        ELSE
            RETURN 'trending_down';
        END IF;
    ELSE
        RETURN 'ranging';
    END IF;
END;
$$ LANGUAGE plpgsql;
