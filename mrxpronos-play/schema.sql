-- Mr XPRONOS Play — D1 / SQLite — 2026-11-18
-- Database: mrxpronos-play-v1 (dedicated; do not use existing Mr XPRONOS production D1)
CREATE TABLE IF NOT EXISTS players (
  user_id TEXT PRIMARY KEY,
  username TEXT NOT NULL DEFAULT '',
  display_name TEXT NOT NULL DEFAULT '',
  confirmed_xp INTEGER NOT NULL DEFAULT 0 CHECK (confirmed_xp >= 0),
  confirmed_taps INTEGER NOT NULL DEFAULT 0 CHECK (confirmed_taps >= 0),
  last_sync_ms INTEGER NOT NULL DEFAULT 0,
  next_sync_ms INTEGER NOT NULL DEFAULT 0,
  last_daily_day TEXT NOT NULL DEFAULT '',
  created_ms INTEGER NOT NULL,
  updated_ms INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS sync_receipts (
  user_id TEXT NOT NULL,
  batch_id TEXT NOT NULL,
  taps INTEGER NOT NULL,
  xp_awarded INTEGER NOT NULL,
  wheel_count INTEGER NOT NULL DEFAULT 0,
  created_ms INTEGER NOT NULL,
  PRIMARY KEY (user_id,batch_id)
);
CREATE TABLE IF NOT EXISTS wheel_claims (
  user_id TEXT NOT NULL,
  day TEXT NOT NULL,
  reward_key TEXT NOT NULL,
  xp_awarded INTEGER NOT NULL,
  created_ms INTEGER NOT NULL,
  PRIMARY KEY (user_id,day)
);
CREATE TABLE IF NOT EXISTS daily_claims (
  user_id TEXT NOT NULL,
  day TEXT NOT NULL,
  xp_awarded INTEGER NOT NULL DEFAULT 100,
  created_ms INTEGER NOT NULL,
  PRIMARY KEY (user_id,day)
);
CREATE INDEX IF NOT EXISTS players_ranking ON players(confirmed_xp DESC);
