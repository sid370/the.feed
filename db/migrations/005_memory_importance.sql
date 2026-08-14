-- Retrieval was recency-only, so "he humiliated me in front of everyone" ranked level with
-- "posted about coffee" and fell out of the window after twelve turns. Park et al. score
-- memories on recency, importance and relevance together; this is the importance term.
-- 5 is the neutral default, so rows written before this column existed rank unchanged.

ALTER TABLE memory_notes
    ADD COLUMN IF NOT EXISTS importance SMALLINT NOT NULL DEFAULT 5;

CREATE INDEX IF NOT EXISTS memory_notes_ranked
    ON memory_notes (character_id, importance DESC, created_at DESC);
