-- Social feed tables for strategy sharing, likes, comments, and follows.

CREATE TABLE shared_strategies (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_id     UUID NOT NULL REFERENCES strategy_specs(id) ON DELETE CASCADE,
    author_id       TEXT NOT NULL,
    author_name     TEXT NOT NULL DEFAULT 'anonymous',
    caption         TEXT NOT NULL DEFAULT '',
    like_count      INTEGER NOT NULL DEFAULT 0,
    comment_count   INTEGER NOT NULL DEFAULT 0,
    shared_at       TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    UNIQUE (strategy_id)
);

CREATE INDEX idx_shared_strategies_shared_at ON shared_strategies (shared_at DESC);
CREATE INDEX idx_shared_strategies_author_id ON shared_strategies (author_id);

CREATE TABLE feed_likes (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shared_strategy_id UUID NOT NULL REFERENCES shared_strategies(id) ON DELETE CASCADE,
    user_id         TEXT NOT NULL,
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    UNIQUE (shared_strategy_id, user_id)
);

CREATE TABLE feed_comments (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shared_strategy_id UUID NOT NULL REFERENCES shared_strategies(id) ON DELETE CASCADE,
    user_id         TEXT NOT NULL,
    user_name       TEXT NOT NULL DEFAULT 'anonymous',
    body            TEXT NOT NULL,
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

CREATE INDEX idx_feed_comments_shared_strategy ON feed_comments (shared_strategy_id, created_at DESC);

CREATE TABLE user_follows (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    follower_id     TEXT NOT NULL,
    followed_id     TEXT NOT NULL,
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    UNIQUE (follower_id, followed_id),
    CHECK (follower_id <> followed_id)
);

CREATE INDEX idx_user_follows_follower ON user_follows (follower_id);
CREATE INDEX idx_user_follows_followed ON user_follows (followed_id);
