-- V17__add_signal_quality_and_beta_onboarding.sql
-- Phase 4: Signal quality scoring tables and beta user onboarding system.
-- References: Issue #1487 (Phase 4 sprint)

-- ============================================================
-- Signal Quality Scoring
-- ============================================================

CREATE TABLE IF NOT EXISTS signal_quality_scores (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    signal_id       UUID NOT NULL,
    strategy_name   TEXT NOT NULL,
    symbol          TEXT NOT NULL,
    confidence      DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    indicator_agreement DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    volume_confirmation DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    trend_alignment DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    volatility_context DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    quality_grade   TEXT NOT NULL DEFAULT 'C',  -- A, B, C, D, F
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_signal_quality_signal ON signal_quality_scores(signal_id);
CREATE INDEX idx_signal_quality_strategy ON signal_quality_scores(strategy_name);
CREATE INDEX idx_signal_quality_grade ON signal_quality_scores(quality_grade);
CREATE INDEX idx_signal_quality_created ON signal_quality_scores(created_at);

-- Signal performance tracking (outcomes)
CREATE TABLE IF NOT EXISTS signal_outcomes (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    signal_id       UUID NOT NULL,
    strategy_name   TEXT NOT NULL,
    symbol          TEXT NOT NULL,
    direction       TEXT NOT NULL,         -- BUY / SELL
    entry_price     DOUBLE PRECISION,
    exit_price      DOUBLE PRECISION,
    pnl_percent     DOUBLE PRECISION,
    outcome         TEXT NOT NULL DEFAULT 'PENDING',  -- WIN, LOSS, PENDING, EXPIRED
    quality_grade   TEXT,
    opened_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    closed_at       TIMESTAMPTZ,
    ttl_bars        INTEGER
);

CREATE INDEX idx_signal_outcomes_strategy ON signal_outcomes(strategy_name);
CREATE INDEX idx_signal_outcomes_outcome ON signal_outcomes(outcome);
CREATE INDEX idx_signal_outcomes_opened ON signal_outcomes(opened_at);

-- Strategy performance summary (materialized view data)
CREATE TABLE IF NOT EXISTS strategy_performance_summary (
    strategy_name   TEXT PRIMARY KEY,
    total_signals   INTEGER NOT NULL DEFAULT 0,
    wins            INTEGER NOT NULL DEFAULT 0,
    losses          INTEGER NOT NULL DEFAULT 0,
    pending         INTEGER NOT NULL DEFAULT 0,
    win_rate        DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    avg_pnl_percent DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    avg_confidence  DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    last_signal_at  TIMESTAMPTZ,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- Beta User Onboarding
-- ============================================================

CREATE TABLE IF NOT EXISTS invite_codes (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code            TEXT UNIQUE NOT NULL,
    created_by      TEXT NOT NULL DEFAULT 'system',
    max_uses        INTEGER NOT NULL DEFAULT 1,
    current_uses    INTEGER NOT NULL DEFAULT 0,
    tier            TEXT NOT NULL DEFAULT 'pro',   -- tier granted on redemption
    expires_at      TIMESTAMPTZ,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX idx_invite_codes_code ON invite_codes(code);

CREATE TABLE IF NOT EXISTS beta_users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id     UUID REFERENCES billing_customers(id),
    invite_code_id  UUID REFERENCES invite_codes(id),
    email           TEXT NOT NULL,
    telegram_chat_id TEXT,
    onboarding_step TEXT NOT NULL DEFAULT 'REGISTERED',  -- REGISTERED, TELEGRAM_CONNECTED, STRATEGY_SELECTED, FIRST_SIGNAL, COMPLETED
    strategies      TEXT[] DEFAULT '{}',
    pairs           TEXT[] DEFAULT '{}',
    welcomed_at     TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_beta_users_email ON beta_users(email);
CREATE INDEX idx_beta_users_step ON beta_users(onboarding_step);
CREATE INDEX idx_beta_users_customer ON beta_users(customer_id);

-- Seed initial batch of invite codes for beta launch
INSERT INTO invite_codes (code, created_by, max_uses, tier, expires_at) VALUES
  ('TRADESTREAM-BETA-001', 'system', 50, 'pro', '2026-06-01'::timestamptz),
  ('TRADESTREAM-BETA-002', 'system', 50, 'pro', '2026-06-01'::timestamptz),
  ('TRADESTREAM-EARLY-VIP', 'system', 25, 'enterprise', '2026-05-01'::timestamptz),
  ('TRADESTREAM-LAUNCH', 'system', 100, 'pro', '2026-07-01'::timestamptz)
ON CONFLICT (code) DO NOTHING;
