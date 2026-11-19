-- Mr XPRONOS Play V2 / Phase 6: security audit for economy balancing.
-- Additive. No player XP, mission, inventory, rank or credit events are modified.
CREATE TABLE IF NOT EXISTS mrxp_balance_audit (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 admin_id TEXT NOT NULL,
 setting_key TEXT NOT NULL,
 old_value TEXT,
 new_value TEXT NOT NULL,
 created_ms INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_mrxp_balance_audit_created ON mrxp_balance_audit(created_ms DESC);
-- Current settings continue to live in bot_settings with the mrxp_balance_ prefix.
