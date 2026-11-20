-- Mr XPRONOS Play / audit 2026-11-20 (lot anti-fraude)
-- Migration additive. Executer avant de deployer le Worker mis a jour.
-- Aucune table de joueurs, aucun solde, historique d'XP, achat ou inventaire n'est efface.
CREATE TABLE IF NOT EXISTS mrxp_reward_intents (
 user_id TEXT NOT NULL,
 kind TEXT NOT NULL CHECK(kind IN ('daily','wheel')),
 day TEXT NOT NULL,
 reward_key TEXT NOT NULL,
 xp_awarded INTEGER NOT NULL CHECK(xp_awarded BETWEEN 1 AND 100),
 claimed_ms INTEGER NOT NULL,
 PRIMARY KEY(user_id,kind,day)
);
CREATE INDEX IF NOT EXISTS idx_mrxp_reward_intents_user_day
 ON mrxp_reward_intents(user_id,day);

-- Bucket de limitation de debit par identite Telegram authentifiee et action.
CREATE TABLE IF NOT EXISTS mrxp_api_limits (
 user_id TEXT NOT NULL,
 action TEXT NOT NULL,
 window_start_ms INTEGER NOT NULL,
 count INTEGER NOT NULL CHECK(count>=1),
 PRIMARY KEY(user_id,action)
);
