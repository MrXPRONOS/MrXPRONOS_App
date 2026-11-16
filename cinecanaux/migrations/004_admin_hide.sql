-- Preserve administrator-initiated hiding independently of technical link health.
ALTER TABLE channel_index_meta ADD COLUMN admin_hidden INTEGER NOT NULL DEFAULT 0 CHECK(admin_hidden IN (0,1));
CREATE INDEX IF NOT EXISTS idx_channel_index_visibility ON channel_index_meta(listing_status,admin_hidden,next_check_at);
