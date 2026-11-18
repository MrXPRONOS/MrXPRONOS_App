-- Observed Telegram channel metadata only; no message text, media, private invite, or account IDs.
-- Unknown/failed checks are not treated as evidence of empty channels.
CREATE TABLE IF NOT EXISTS owned_channel_quality (
  channel_id INTEGER PRIMARY KEY REFERENCES channels(id) ON DELETE CASCADE,
  avatar_status TEXT NOT NULL DEFAULT 'unknown' CHECK(avatar_status IN ('real','fallback','unknown')),
  avatar_checked_at TEXT,
  total_posts INTEGER CHECK(total_posts IS NULL OR total_posts>=0),
  sampled_posts INTEGER NOT NULL DEFAULT 0 CHECK(sampled_posts>=0),
  posts_7d INTEGER CHECK(posts_7d IS NULL OR posts_7d>=0),
  posts_30d INTEGER CHECK(posts_30d IS NULL OR posts_30d>=0),
  media_30d INTEGER CHECK(media_30d IS NULL OR media_30d>=0),
  last_post_at TEXT,
  audit_status TEXT NOT NULL DEFAULT 'unknown' CHECK(audit_status IN ('verified','unavailable','unknown')),
  observed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_owned_quality_rank ON owned_channel_quality(avatar_status,posts_30d,total_posts);
