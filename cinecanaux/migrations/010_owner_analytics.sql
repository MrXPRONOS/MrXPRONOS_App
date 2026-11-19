-- Cine Radar: private owner claim and privacy-first aggregate usage reporting.
CREATE TABLE IF NOT EXISTS owner_claim_request(
 id INTEGER PRIMARY KEY CHECK(id=1),
 username TEXT NOT NULL,
 code_sha256 TEXT NOT NULL,
 expires_at TEXT NOT NULL,
 used_at TEXT,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS analytics_bot_users(
 visitor_hash TEXT PRIMARY KEY,
 first_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 last_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 starts INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_analytics_bot_seen ON analytics_bot_users(last_seen_at);
CREATE TABLE IF NOT EXISTS analytics_bot_days(
 visitor_hash TEXT NOT NULL,
 day_utc TEXT NOT NULL,
 starts INTEGER NOT NULL DEFAULT 0,
 PRIMARY KEY(visitor_hash,day_utc)
);
CREATE INDEX IF NOT EXISTS idx_analytics_bot_day ON analytics_bot_days(day_utc);
CREATE TABLE IF NOT EXISTS analytics_app_visitors(
 visitor_hash TEXT PRIMARY KEY,
 first_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 last_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_analytics_app_seen ON analytics_app_visitors(last_seen_at);
CREATE TABLE IF NOT EXISTS analytics_app_days(
 visitor_hash TEXT NOT NULL,
 day_utc TEXT NOT NULL,
 visits INTEGER NOT NULL DEFAULT 0,
 PRIMARY KEY(visitor_hash,day_utc)
);
CREATE INDEX IF NOT EXISTS idx_analytics_app_day ON analytics_app_days(day_utc);
CREATE TABLE IF NOT EXISTS analytics_events_daily(
 day_utc TEXT NOT NULL,
 event_name TEXT NOT NULL CHECK(event_name IN ('channel_open','pin_open','promo_open','share','rating')),
 target_key TEXT NOT NULL,
 hits INTEGER NOT NULL DEFAULT 0,
 PRIMARY KEY(day_utc,event_name,target_key)
);
CREATE INDEX IF NOT EXISTS idx_analytics_event_day ON analytics_events_daily(day_utc,event_name);
