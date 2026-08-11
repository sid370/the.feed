-- Batch results already carry per-request token usage and it was being discarded.
-- cache_read_tokens is the only signal that prompt caching is actually working; a silent
-- invalidator shows up here as zero and nowhere else.

ALTER TABLE batches
    ADD COLUMN IF NOT EXISTS input_tokens       BIGINT NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS output_tokens      BIGINT NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS cache_read_tokens  BIGINT NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS cache_write_tokens BIGINT NOT NULL DEFAULT 0;
