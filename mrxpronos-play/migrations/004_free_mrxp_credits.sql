-- Mr XPRONOS Play V2, Phase 4: free nontransferable credits.
-- Ledger is append-only and unique per server-verified earning event.
-- No client-supplied credit amounts and no purchases in this phase.
CREATE TABLE IF NOT EXISTS player_credit_state (
  user_id TEXT PRIMARY KEY REFERENCES players(user_id),
  baseline_level INTEGER NOT NULL CHECK(baseline_level BETWEEN 1 AND 50),
  activated_ms INTEGER NOT NULL CHECK(activated_ms>0)
);
CREATE TABLE IF NOT EXISTS mrxp_credit_events (
  user_id TEXT NOT NULL REFERENCES players(user_id),
  event_key TEXT NOT NULL,
  event_type TEXT NOT NULL,
  amount INTEGER NOT NULL CHECK(amount <> 0),
  label TEXT NOT NULL,
  created_ms INTEGER NOT NULL,
  PRIMARY KEY(user_id,event_key)
);
CREATE INDEX IF NOT EXISTS idx_mrxp_credit_history ON mrxp_credit_events(user_id,created_ms DESC);
-- Freeze historical level at economy activation; only *future* verified actions
-- produce MRXP credits. Existing XP and historical rewards are untouched.
INSERT OR IGNORE INTO player_credit_state(user_id,baseline_level,activated_ms)
 SELECT p.user_id,COALESCE(v.current_level,1),CAST(strftime('%s','now') AS INTEGER)*1000
 FROM players p LEFT JOIN player_progress_v2 v ON v.user_id=p.user_id;
