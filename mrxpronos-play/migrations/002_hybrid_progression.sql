-- Mr XPRONOS Play V2 — phase 1 : hybrid levels + mastery gates
-- Additive / safe to run more than once. Preserves all player XP, claimed missions,
-- daily bonuses, wheel spins, pending sync receipts and the current bot configuration.
CREATE TABLE IF NOT EXISTS player_progress_v2 (
  user_id TEXT PRIMARY KEY REFERENCES players(user_id),
  legacy_level_floor INTEGER NOT NULL DEFAULT 1 CHECK (legacy_level_floor >= 1),
  current_level INTEGER NOT NULL DEFAULT 1 CHECK (current_level >= 1),
  created_ms INTEGER NOT NULL,
  updated_ms INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_player_progress_v2_level ON player_progress_v2(current_level DESC);
-- The initial legacy level is frozen the first time each real Telegram user
-- authenticates after deployment. Existing scores are NEVER reset or reduced.
-- Verified mastery uses existing audit ledgers: sync_receipts / mission_claims /
-- daily_claims / wheel_claims; no synthetic rewards or arbitrary level requests.
