-- Mr XPRONOS Play V2 phase 5: free, non-transferable shop inventory.
-- Additive migration: do not mutate player XP, missions, profiles or existing MRXP events.
CREATE TABLE IF NOT EXISTS mrxp_boost_inventory (
 user_id TEXT NOT NULL REFERENCES players(user_id),
 purchase_id TEXT NOT NULL,
 sku TEXT NOT NULL,
 kind TEXT NOT NULL CHECK(kind IN ('tap','energy')),
 cost INTEGER NOT NULL CHECK(cost>0),
 state TEXT NOT NULL DEFAULT 'owned' CHECK(state IN ('owned','queued','active','charged','used','expired')),
 bought_ms INTEGER NOT NULL,
 activated_ms INTEGER NOT NULL DEFAULT 0,
 expires_ms INTEGER NOT NULL DEFAULT 0,
 carry_milli INTEGER NOT NULL DEFAULT 0 CHECK(carry_milli BETWEEN 0 AND 999),
 PRIMARY KEY(user_id,purchase_id)
);
CREATE INDEX IF NOT EXISTS idx_mrxp_boost_active ON mrxp_boost_inventory(user_id,kind,state,expires_ms);
-- Purchases debit the phase 4 mrxp_credit_events ledger with a stable buy:<purchase_id> event.
-- A single D1 transaction pairs every inventory row with its debit; no other account can spend it.
