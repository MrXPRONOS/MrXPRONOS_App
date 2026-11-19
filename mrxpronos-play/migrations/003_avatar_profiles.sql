-- Mr XPRONOS Play V2 — Phase 2: secure cosmetic avatar choice (additive)
-- Never changes XP, rank thresholds, missions, or historic level floors.
-- selected_rank = 0 means "automatically follow my highest unlocked rank".
CREATE TABLE IF NOT EXISTS player_avatar_prefs (
  user_id TEXT PRIMARY KEY REFERENCES players(user_id),
  selected_rank INTEGER NOT NULL DEFAULT 0 CHECK (selected_rank BETWEEN 0 AND 11),
  updated_ms INTEGER NOT NULL
);
-- User ID is taken exclusively from server-verified Telegram initData.
