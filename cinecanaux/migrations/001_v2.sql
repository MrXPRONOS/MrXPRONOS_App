-- Cine Radar V2: additive, backward-compatible migration for Cloudflare D1.
-- Run once on a staging D1 database before deploying new Worker code.
CREATE TABLE IF NOT EXISTS channel_index_meta (
 channel_id INTEGER PRIMARY KEY REFERENCES channels(id) ON DELETE CASCADE,
 listing_status TEXT NOT NULL DEFAULT 'listed' CHECK(listing_status IN ('listed','checking','hidden','excluded')),
 last_checked_at TEXT,
 next_check_at TEXT,
 consecutive_failures INTEGER NOT NULL DEFAULT 0,
 first_failure_at TEXT,
 last_healthy_at TEXT,
 link_status TEXT NOT NULL DEFAULT 'unknown' CHECK(link_status IN ('unknown','reachable','unverifiable','not_found','private')),
 quality_score REAL NOT NULL DEFAULT 0,
 updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_index_meta_due ON channel_index_meta(listing_status,next_check_at,last_checked_at);
CREATE TABLE IF NOT EXISTS channel_categories (
 channel_id INTEGER NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
 category TEXT NOT NULL,
 PRIMARY KEY(channel_id,category)
);
CREATE INDEX IF NOT EXISTS idx_channel_categories_category ON channel_categories(category);
CREATE TABLE IF NOT EXISTS channel_reviews (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 channel_id INTEGER NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
 telegram_user_hash TEXT NOT NULL,
 rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
 matches_description TEXT NOT NULL CHECK(matches_description IN ('yes','part','no')),
 comment TEXT NOT NULL DEFAULT '' CHECK(length(comment)<=500),
 visibility TEXT NOT NULL DEFAULT 'visible' CHECK(visibility IN ('visible','held','hidden')),
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE(channel_id,telegram_user_hash)
);
CREATE INDEX IF NOT EXISTS idx_reviews_channel ON channel_reviews(channel_id,visibility);
CREATE TABLE IF NOT EXISTS channel_reports (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 channel_id INTEGER NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
 telegram_user_hash TEXT NOT NULL,
 reason TEXT NOT NULL CHECK(reason IN ('wrong_category','misleading','dead_link','spam','copyright','other')),
 details TEXT NOT NULL DEFAULT '' CHECK(length(details)<=500),
 status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open','reviewing','resolved','dismissed')),
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE(channel_id,telegram_user_hash,reason)
);
CREATE INDEX IF NOT EXISTS idx_reports_status ON channel_reports(status,created_at);
CREATE TABLE IF NOT EXISTS channel_suggestions (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 telegram_user_hash TEXT NOT NULL,
 link TEXT NOT NULL,
 username TEXT NOT NULL COLLATE NOCASE,
 suggested_category TEXT NOT NULL CHECK(suggested_category IN ('films','series','animes')),
 status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','indexed','rejected','unverifiable')),
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE(username)
);
CREATE INDEX IF NOT EXISTS idx_suggestions_status ON channel_suggestions(status,created_at);
CREATE TABLE IF NOT EXISTS channel_exclusions (
 username TEXT PRIMARY KEY COLLATE NOCASE,
 reason TEXT NOT NULL,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS channel_aliases (
 username TEXT PRIMARY KEY COLLATE NOCASE,
 channel_id INTEGER NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
 discovered_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 verified_at TEXT
);
CREATE TABLE IF NOT EXISTS channel_checks (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 channel_id INTEGER NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
 checked_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 outcome TEXT NOT NULL CHECK(outcome IN ('reachable','unverifiable','not_found','private')),
 old_link TEXT NOT NULL,
 new_link TEXT,
 details TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_channel_checks_recent ON channel_checks(channel_id,checked_at);
INSERT OR IGNORE INTO channel_index_meta(channel_id) SELECT id FROM channels;
INSERT OR IGNORE INTO channel_categories(channel_id,category) SELECT id,content_type FROM channels WHERE content_type IN ('films','series','animes');
