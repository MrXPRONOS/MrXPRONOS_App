PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, created_at INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS products (
 id TEXT PRIMARY KEY, title TEXT NOT NULL, category TEXT NOT NULL, description TEXT NOT NULL,
 price_xof INTEGER NOT NULL CHECK(price_xof>=0), active INTEGER NOT NULL DEFAULT 0 CHECK(active IN(0,1)),
 object_key TEXT, file_id TEXT, filename TEXT NOT NULL, cover_key TEXT, cover_file_id TEXT,
 CHECK(length(id) BETWEEN 1 AND 24)
);
CREATE TABLE IF NOT EXISTS campaigns (
 id TEXT PRIMARY KEY, product_id TEXT NOT NULL REFERENCES products(id), channel_id TEXT NOT NULL,
 channel_url TEXT NOT NULL, target INTEGER NOT NULL CHECK(target BETWEEN 1 AND 20),
 hold_seconds INTEGER NOT NULL DEFAULT 86400 CHECK(hold_seconds>=0), active INTEGER NOT NULL DEFAULT 0 CHECK(active IN(0,1)),
 CHECK(length(id) BETWEEN 1 AND 24)
);
CREATE TABLE IF NOT EXISTS links (
 campaign_id TEXT NOT NULL REFERENCES campaigns(id), owner_id TEXT NOT NULL REFERENCES users(id),
 invite_link TEXT NOT NULL UNIQUE, channel_id TEXT NOT NULL, created_at INTEGER NOT NULL,
 PRIMARY KEY(campaign_id,owner_id)
);
CREATE TABLE IF NOT EXISTS memberships (
 channel_id TEXT NOT NULL, user_id TEXT NOT NULL, present INTEGER NOT NULL CHECK(present IN(0,1)),
 last_event INTEGER NOT NULL, last_update INTEGER NOT NULL, PRIMARY KEY(channel_id,user_id)
);
CREATE TABLE IF NOT EXISTS referrals (
 channel_id TEXT NOT NULL, invitee_id TEXT NOT NULL, campaign_id TEXT NOT NULL REFERENCES campaigns(id),
 owner_id TEXT NOT NULL REFERENCES users(id), joined_at INTEGER NOT NULL, eligible_at INTEGER NOT NULL,
 state TEXT NOT NULL CHECK(state IN('pending','valid','rejected')), reason TEXT,
 PRIMARY KEY(channel_id,invitee_id), CHECK(invitee_id<>owner_id)
);
CREATE INDEX IF NOT EXISTS ref_owner ON referrals(campaign_id,owner_id,state);
CREATE INDEX IF NOT EXISTS ref_due ON referrals(state,eligible_at);
CREATE TABLE IF NOT EXISTS entitlements (
 user_id TEXT NOT NULL REFERENCES users(id), product_id TEXT NOT NULL REFERENCES products(id),
 source TEXT NOT NULL CHECK(source IN('free','referral','purchase','admin')), created_at INTEGER NOT NULL,
 PRIMARY KEY(user_id,product_id)
);
CREATE TABLE IF NOT EXISTS deliveries (user_id TEXT NOT NULL,product_id TEXT NOT NULL,delivered_at INTEGER NOT NULL,
 PRIMARY KEY(user_id,product_id));
CREATE TABLE IF NOT EXISTS updates (id INTEGER PRIMARY KEY, state TEXT NOT NULL, lease_until INTEGER NOT NULL, created_at INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS audit (id INTEGER PRIMARY KEY AUTOINCREMENT, admin_id TEXT NOT NULL, action TEXT NOT NULL, target TEXT NOT NULL, created_at INTEGER NOT NULL);
