CREATE TABLE IF NOT EXISTS owned_channels(id INTEGER PRIMARY KEY AUTOINCREMENT,chat_id TEXT NOT NULL UNIQUE,title TEXT NOT NULL,link TEXT NOT NULL,enabled INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS channels(id INTEGER PRIMARY KEY AUTOINCREMENT,title TEXT NOT NULL,link TEXT NOT NULL UNIQUE,description TEXT DEFAULT '',content_type TEXT NOT NULL,genre TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'pending',rights_confirmed INTEGER NOT NULL DEFAULT 0,updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS suggestions(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,link TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'pending',created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS user_states(user_id INTEGER PRIMARY KEY,mode TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS update_log(update_id INTEGER PRIMARY KEY,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE INDEX IF NOT EXISTS idx_channels_search ON channels(status,content_type,genre);

CREATE TABLE IF NOT EXISTS discovery_candidates (
 username TEXT PRIMARY KEY COLLATE NOCASE,
 title TEXT NOT NULL,
 link TEXT NOT NULL,
 content_type TEXT NOT NULL CHECK(content_type IN ('films','series','animes')),
 genre TEXT NOT NULL,
 source_category TEXT NOT NULL,
 matching_pairs INTEGER NOT NULL DEFAULT 0,
 technical_status TEXT NOT NULL CHECK(technical_status IN ('qualified','rejected_format')),
 rights_status TEXT NOT NULL DEFAULT 'unverified',
 first_seen TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 last_seen TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 last_scan TEXT NOT NULL,
 updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_discovery_status ON discovery_candidates(technical_status,rights_status,content_type,genre);
CREATE TABLE IF NOT EXISTS discovery_sync_status (
 id INTEGER PRIMARY KEY CHECK(id=1),
 scan_date TEXT NOT NULL,
 imported INTEGER NOT NULL DEFAULT 0,
 qualified INTEGER NOT NULL DEFAULT 0,
 rejected INTEGER NOT NULL DEFAULT 0,
 last_error TEXT NOT NULL DEFAULT '',
 updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS bot_webhook_status (
 id INTEGER PRIMARY KEY CHECK(id=1),
 status TEXT NOT NULL,
 detail TEXT NOT NULL DEFAULT '',
 updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Code personnel de parrainage opaque.
CREATE TABLE IF NOT EXISTS referral_codes (
  user_id INTEGER PRIMARY KEY,
  code TEXT NOT NULL UNIQUE,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
-- Un filleul ne peut être attribué qu'à un seul parrain et jamais à lui-même.
CREATE TABLE IF NOT EXISTS referral_visits (
  invited_id INTEGER PRIMARY KEY,
  referrer_id INTEGER NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  confirmed_at TEXT,
  CHECK (invited_id <> referrer_id)
);
CREATE INDEX IF NOT EXISTS idx_referral_visits_referrer ON referral_visits(referrer_id,confirmed_at);


-- Cine Radar V2: favorites, filters, moderation, notifications, metrics.
CREATE TABLE IF NOT EXISTS favorites (
 user_id INTEGER NOT NULL,channel_id INTEGER NOT NULL,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY(user_id,channel_id));
CREATE TABLE IF NOT EXISTS preferences (
 user_id INTEGER PRIMARY KEY,category TEXT NOT NULL DEFAULT 'films',
 language TEXT NOT NULL DEFAULT 'tous',notification_enabled INTEGER NOT NULL DEFAULT 0,
 onboarded INTEGER NOT NULL DEFAULT 0,updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS channel_reports (
 id INTEGER PRIMARY KEY AUTOINCREMENT,channel_id INTEGER NOT NULL,user_id INTEGER NOT NULL,
 reason TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'open',created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE(channel_id,user_id,reason));
CREATE TABLE IF NOT EXISTS channel_telemetry (
 channel_id INTEGER PRIMARY KEY,opens INTEGER NOT NULL DEFAULT 0,shares INTEGER NOT NULL DEFAULT 0,
 check_status TEXT NOT NULL DEFAULT 'unknown',last_checked_at TEXT,last_good_at TEXT);
CREATE TABLE IF NOT EXISTS bot_settings (
 setting_key TEXT PRIMARY KEY,value TEXT NOT NULL,updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS admin_users (
 user_id INTEGER PRIMARY KEY,role TEXT NOT NULL DEFAULT 'admin',created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS channel_moderation_log (
 id INTEGER PRIMARY KEY AUTOINCREMENT,channel_id INTEGER NOT NULL,
 admin_id INTEGER NOT NULL,action TEXT NOT NULL,evidence TEXT NOT NULL DEFAULT '',
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS notices_sent (
 user_id INTEGER NOT NULL,channel_id INTEGER NOT NULL,PRIMARY KEY(user_id,channel_id));
CREATE INDEX IF NOT EXISTS idx_channels_approved_recent ON channels(status,rights_confirmed,updated_at);
CREATE INDEX IF NOT EXISTS idx_reports_pending ON channel_reports(status,created_at);
-- For existing D1 databases, apply the ALTER TABLE statements below once.
-- ALTER TABLE channels ADD COLUMN language TEXT NOT NULL DEFAULT 'VF';
-- ALTER TABLE channels ADD COLUMN verified_at TEXT;
-- ALTER TABLE channels ADD COLUMN last_post_at TEXT;
-- ALTER TABLE channels ADD COLUMN rights_evidence TEXT NOT NULL DEFAULT '';
-- ALTER TABLE channels ADD COLUMN banner_url TEXT NOT NULL DEFAULT '';
