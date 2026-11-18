-- Ciné Radar: promote channels managed by a verified Telegram administrator.
-- Promotion is distinct from the community quality score or a verification badge.
CREATE TABLE IF NOT EXISTS owned_channel_features(
 channel_id INTEGER PRIMARY KEY REFERENCES channels(id) ON DELETE CASCADE,
 source TEXT NOT NULL DEFAULT 'telegram_admin_registry',
 verification TEXT NOT NULL DEFAULT 'bot_admin' CHECK(verification IN ('bot_admin','both_admins')),
 featured_since TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 last_verified_at TEXT,
 priority INTEGER NOT NULL DEFAULT 1 CHECK(priority BETWEEN 1 AND 5),
 PRIMARY_category TEXT NOT NULL CHECK(PRIMARY_category IN ('films','series','animes')),
 private_channel INTEGER NOT NULL DEFAULT 0 CHECK(private_channel IN (0,1)),
 telegram_chat_id TEXT,
 enabled INTEGER NOT NULL DEFAULT 1 CHECK(enabled IN (0,1))
);
CREATE INDEX IF NOT EXISTS idx_owned_features_category ON owned_channel_features(enabled,PRIMARY_category,priority);
