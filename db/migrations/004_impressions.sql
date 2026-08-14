-- What each character has already been shown. Without it a post can be re-served to the
-- same character every tick forever, which is a repetition source no prompt can fix.

CREATE TABLE IF NOT EXISTS impressions (
    character_id UUID NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    post_id      UUID NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (character_id, post_id)
);

CREATE INDEX IF NOT EXISTS impressions_recent ON impressions (character_id, created_at DESC);
