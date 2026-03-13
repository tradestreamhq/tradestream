-- Trade journal: entries with emotion tracking, tags, and screenshots for reviewing trading decisions.

CREATE TABLE IF NOT EXISTS trade_journal (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trade_id        UUID REFERENCES paper_trades(id) ON DELETE SET NULL,
    entry_notes     TEXT        NOT NULL DEFAULT '',
    exit_notes      TEXT        NOT NULL DEFAULT '',
    emotion_tag     VARCHAR(20) CHECK (emotion_tag IN ('confident', 'fearful', 'neutral', 'greedy')),
    lesson_learned  TEXT        NOT NULL DEFAULT '',
    rating          INTEGER     CHECK (rating >= 1 AND rating <= 5),
    screenshots_urls TEXT[]     NOT NULL DEFAULT '{}',
    created_at      TIMESTAMP   NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP   NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_trade_journal_trade_id ON trade_journal(trade_id);
CREATE INDEX IF NOT EXISTS idx_trade_journal_emotion_tag ON trade_journal(emotion_tag);
CREATE INDEX IF NOT EXISTS idx_trade_journal_rating ON trade_journal(rating);
CREATE INDEX IF NOT EXISTS idx_trade_journal_created_at ON trade_journal(created_at);

CREATE TABLE IF NOT EXISTS journal_tags (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    journal_id      UUID NOT NULL REFERENCES trade_journal(id) ON DELETE CASCADE,
    tag             VARCHAR(100) NOT NULL,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_journal_tags_journal_id ON journal_tags(journal_id);
CREATE INDEX IF NOT EXISTS idx_journal_tags_tag ON journal_tags(tag);

-- Auto-update updated_at trigger
CREATE OR REPLACE FUNCTION update_trade_journal_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trade_journal_updated_at ON trade_journal;
CREATE TRIGGER trade_journal_updated_at
    BEFORE UPDATE ON trade_journal
    FOR EACH ROW
    EXECUTE FUNCTION update_trade_journal_updated_at();
