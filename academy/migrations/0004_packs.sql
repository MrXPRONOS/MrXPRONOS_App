-- V1.6: user-composed referral bundles.
CREATE TABLE IF NOT EXISTS referral_packs (
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id), signature TEXT NOT NULL,
 token TEXT NOT NULL UNIQUE, target INTEGER NOT NULL CHECK(target BETWEEN 1 AND 100),
 original_target INTEGER NOT NULL, created_at INTEGER NOT NULL,
 UNIQUE(owner_id,signature)
);
CREATE TABLE IF NOT EXISTS referral_pack_items (
 pack_id TEXT NOT NULL REFERENCES referral_packs(id), product_id TEXT NOT NULL REFERENCES products(id),
 campaign_id TEXT NOT NULL REFERENCES campaigns(id), position INTEGER NOT NULL,
 PRIMARY KEY(pack_id,product_id)
);
CREATE TABLE IF NOT EXISTS referral_pack_visits (
 pack_id TEXT NOT NULL REFERENCES referral_packs(id), visitor_id TEXT NOT NULL REFERENCES users(id),
 created_at INTEGER NOT NULL, PRIMARY KEY(pack_id,visitor_id)
);
CREATE INDEX IF NOT EXISTS pack_owner ON referral_packs(owner_id,created_at);
CREATE INDEX IF NOT EXISTS pack_items_campaign ON referral_pack_items(campaign_id);
