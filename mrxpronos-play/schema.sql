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

-- Trace non sensible de l'activation Telegram, aucun token stocké ici.
CREATE TABLE IF NOT EXISTS telegram_setup_status (
  id TEXT PRIMARY KEY,
  status TEXT NOT NULL,
  bot_username TEXT NOT NULL DEFAULT '',
  webhook_url TEXT NOT NULL DEFAULT '',
  menu_type TEXT NOT NULL DEFAULT '',
  error TEXT NOT NULL DEFAULT '',
  updated_ms INTEGER NOT NULL
);

-- Telegram bot administration (additive migration, no account identifier in code).
CREATE TABLE IF NOT EXISTS bot_admins (
  telegram_id TEXT PRIMARY KEY,
  created_ms INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS bot_settings (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL,
  updated_ms INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS bot_admin_pending (
  telegram_id TEXT PRIMARY KEY,
  edit_key TEXT NOT NULL,
  expires_ms INTEGER NOT NULL
);
-- Game feature flags use bot_settings keys feature_tap, feature_wheel,
-- feature_daily, feature_missions. Missing keys mean enabled by default.

-- Rewards engine: unique one-time bonus for each completed mission (idempotent).
CREATE TABLE IF NOT EXISTS mission_claims (
  user_id TEXT NOT NULL,
  mission_key TEXT NOT NULL,
  xp_awarded INTEGER NOT NULL CHECK (xp_awarded >= 0),
  created_ms INTEGER NOT NULL,
  PRIMARY KEY (user_id, mission_key)
);
CREATE INDEX IF NOT EXISTS idx_mission_claims_user ON mission_claims(user_id);
-- Existing users and XP totals are preserved; no points are retroactively
-- awarded until a valid mission claim is submitted and checked by the Worker.


-- V2 Phase 1: official XP level with mastery gates and frozen legacy floor.
-- The old players.confirmed_xp and players.confirmed_taps remain untouched.
CREATE TABLE IF NOT EXISTS player_progress_v2 (
 user_id TEXT PRIMARY KEY REFERENCES players(user_id),
 legacy_level_floor INTEGER NOT NULL DEFAULT 1 CHECK (legacy_level_floor>=1),
 current_level INTEGER NOT NULL DEFAULT 1 CHECK (current_level>=1),
 created_ms INTEGER NOT NULL,
 updated_ms INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_player_progress_v2_level ON player_progress_v2(current_level DESC);
