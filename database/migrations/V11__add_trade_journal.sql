-- Trade journal: auto-logged entries with tags for reviewing trading decisions.

CREATE TABLE IF NOT EXISTS journal_entries (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    instrument      TEXT        NOT NULL,
    side            TEXT        NOT NULL CHECK (side IN ('BUY', 'SELL')),
    entry_price     NUMERIC     NOT NULL,
    exit_price      NUMERIC,
    size            NUMERIC     NOT NULL,
    pnl             NUMERIC,
    outcome         TEXT        CHECK (outcome IN ('WIN', 'LOSS', 'OPEN')),
    strategy_name   TEXT,
    signal_trigger  TEXT,
    notes           TEXT        DEFAULT '',
    opened_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    closed_at       TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS journal_tags (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entry_id        UUID        NOT NULL REFERENCES journal_entries(id) ON DELETE CASCADE,
    tag             TEXT        NOT NULL,
    UNIQUE (entry_id, tag)
);

CREATE INDEX idx_journal_entries_strategy   ON journal_entries (strategy_name);
CREATE INDEX idx_journal_entries_outcome    ON journal_entries (outcome);
CREATE INDEX idx_journal_entries_opened_at  ON journal_entries (opened_at);
CREATE INDEX idx_journal_tags_tag          ON journal_tags (tag);
CREATE INDEX idx_journal_entries_notes_trgm ON journal_entries USING gin (notes gin_trgm_ops);
