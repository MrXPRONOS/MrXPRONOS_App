-- No raw IP addresses or Telegram user IDs; one rotating SHA-256 hash per
-- client/minute/endpoint. Entries are purged after the fixed expiration window.
CREATE TABLE IF NOT EXISTS cine_public_event_buckets (
 bucket_hash TEXT PRIMARY KEY CHECK(length(bucket_hash)=64),
 hits INTEGER NOT NULL DEFAULT 0 CHECK(hits>=0),
 expires_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cine_public_event_buckets_expiry ON cine_public_event_buckets(expires_at);
