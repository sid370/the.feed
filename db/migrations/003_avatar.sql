-- One column holds either source: a path under web/public ("/avatars/elonmusk.png") or a
-- full external URL. NULL keeps the generated initials avatar, so the cast renders before
-- a single image exists.

ALTER TABLE characters
    ADD COLUMN IF NOT EXISTS avatar_url TEXT;
