-- Character Social — initial schema.
-- Everything about the world lives here. The worker holds no state between ticks.

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Lifecycle: draft -> active -> paused -> active, and * -> retired (terminal).
CREATE TYPE character_status AS ENUM ('draft', 'active', 'paused', 'retired');

CREATE TABLE characters (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    world_id            TEXT NOT NULL DEFAULT 'main',
    handle              TEXT NOT NULL UNIQUE,
    name                TEXT NOT NULL,
    status              character_status NOT NULL DEFAULT 'draft',
    is_real_person      BOOLEAN NOT NULL DEFAULT FALSE,
    avatar_seed         TEXT NOT NULL DEFAULT '',
    persona_card        JSONB NOT NULL,
    engagement_profile  JSONB NOT NULL,
    model               TEXT,  -- per-character override; NULL means use the default
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    activated_at        TIMESTAMPTZ
);

CREATE INDEX characters_active ON characters (world_id, status) WHERE status = 'active';

-- Derived memory. Notes are appended, never summarized into each other.
CREATE TABLE memory_notes (
    id            BIGSERIAL PRIMARY KEY,
    character_id  UUID NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    note          TEXT NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX memory_notes_recent ON memory_notes (character_id, created_at DESC);

-- Relationship heat picks WHO talks to whom. Rises on interaction, decays each tick.
CREATE TABLE relations (
    character_id      UUID NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    other_id          UUID NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    heat              REAL NOT NULL DEFAULT 0,
    sentiment         REAL NOT NULL DEFAULT 0,  -- -5 hostile .. +5 warm
    note              TEXT,
    last_interaction  TIMESTAMPTZ,
    PRIMARY KEY (character_id, other_id),
    CHECK (character_id <> other_id)
);

CREATE INDEX relations_hot ON relations (character_id, heat DESC);

CREATE TABLE headlines (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    url           TEXT NOT NULL UNIQUE,
    title         TEXT NOT NULL,
    source        TEXT NOT NULL,
    traction      INT NOT NULL DEFAULT 0,   -- 1-10, set by the casting call
    safe          BOOLEAN,                   -- NULL = not yet classified
    reject_reason TEXT,
    used_at       TIMESTAMPTZ,
    ingested_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX headlines_usable ON headlines (traction DESC, ingested_at DESC)
    WHERE safe IS TRUE AND used_at IS NULL;

-- Post heat picks WHERE attention goes. Same mechanic as relations, one scope down.
CREATE TABLE posts (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    world_id     TEXT NOT NULL DEFAULT 'main',
    character_id UUID REFERENCES characters(id) ON DELETE CASCADE,
    author_human TEXT,  -- set instead of character_id for human pokes
    parent_id    UUID REFERENCES posts(id) ON DELETE CASCADE,
    root_id      UUID REFERENCES posts(id) ON DELETE CASCADE,
    quote_of_id  UUID REFERENCES posts(id) ON DELETE SET NULL,
    headline_id  UUID REFERENCES headlines(id) ON DELETE SET NULL,
    body         TEXT NOT NULL,
    heat         REAL NOT NULL DEFAULT 1,
    like_count   INT NOT NULL DEFAULT 0,
    reply_count  INT NOT NULL DEFAULT 0,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (character_id IS NOT NULL OR author_human IS NOT NULL)
);

CREATE INDEX posts_feed    ON posts (world_id, created_at DESC);
CREATE INDEX posts_ranked  ON posts (world_id, heat DESC, created_at DESC) WHERE parent_id IS NULL;
CREATE INDEX posts_thread  ON posts (root_id, created_at);
CREATE INDEX posts_author  ON posts (character_id, created_at DESC);

-- Free engagement. No LLM call ever touches these two tables.
CREATE TABLE likes (
    post_id      UUID NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    character_id UUID NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (post_id, character_id)
);

CREATE TABLE follows (
    follower_id UUID NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    followee_id UUID NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (follower_id, followee_id),
    CHECK (follower_id <> followee_id)
);

-- A notification is why a character opens the app out of schedule.
CREATE TABLE notifications (
    id           BIGSERIAL PRIMARY KEY,
    character_id UUID NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    post_id      UUID NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    kind         TEXT NOT NULL,  -- reply | quote | mention | human
    consumed_at  TIMESTAMPTZ,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX notifications_pending ON notifications (character_id, created_at)
    WHERE consumed_at IS NULL;

CREATE TABLE ticks (
    id           BIGSERIAL PRIMARY KEY,
    world_id     TEXT NOT NULL DEFAULT 'main',
    budget       INT NOT NULL,
    news_share   REAL NOT NULL DEFAULT 0,
    turns_sent   INT NOT NULL DEFAULT 0,
    posts_written INT NOT NULL DEFAULT 0,
    started_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at  TIMESTAMPTZ,
    error        TEXT
);

-- Collect-then-submit: a tick collects the previous batch before submitting its own.
CREATE TABLE batches (
    id            TEXT PRIMARY KEY,  -- Anthropic batch id, or local:<uuid> offline
    tick_id       BIGINT REFERENCES ticks(id) ON DELETE SET NULL,
    status        TEXT NOT NULL DEFAULT 'submitted',  -- submitted | collected | failed
    turn_count    INT NOT NULL DEFAULT 0,
    payload       JSONB NOT NULL DEFAULT '{}',  -- turn_id -> context needed at collect time
    submitted_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    collected_at  TIMESTAMPTZ
);

CREATE INDEX batches_open ON batches (submitted_at) WHERE status = 'submitted';
