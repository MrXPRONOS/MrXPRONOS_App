-- First participation per product. Original channel membership records remain intact.
CREATE TABLE IF NOT EXISTS discovery_links (
 campaign_id TEXT NOT NULL REFERENCES campaigns(id), owner_id TEXT NOT NULL REFERENCES users(id),
 token TEXT NOT NULL UNIQUE, created_at INTEGER NOT NULL,
 PRIMARY KEY(campaign_id,owner_id)
);
CREATE TABLE IF NOT EXISTS discovery_visits (
 product_id TEXT NOT NULL REFERENCES products(id), visitor_id TEXT NOT NULL REFERENCES users(id),
 campaign_id TEXT NOT NULL REFERENCES campaigns(id), owner_id TEXT REFERENCES users(id), created_at INTEGER NOT NULL,
 PRIMARY KEY(product_id,visitor_id), CHECK(owner_id IS NULL OR owner_id<>visitor_id)
);
CREATE INDEX IF NOT EXISTS discovery_owner ON discovery_visits(campaign_id,owner_id);
