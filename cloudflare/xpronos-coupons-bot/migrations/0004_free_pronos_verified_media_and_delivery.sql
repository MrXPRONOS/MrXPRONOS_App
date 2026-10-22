-- Free Pronos V3: media references, structured results and delivery auditing.
ALTER TABLE coupons ADD COLUMN competition TEXT;
ALTER TABLE coupons ADD COLUMN media_json TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(media_json));
ALTER TABLE coupons ADD COLUMN auto_settlement INTEGER NOT NULL DEFAULT 0 CHECK(auto_settlement IN (0,1));
ALTER TABLE coupons ADD COLUMN settlement_report TEXT;
ALTER TABLE coupons ADD COLUMN settlement_checked_at TEXT;
ALTER TABLE coupons ADD COLUMN provider TEXT NOT NULL DEFAULT 'manual';
CREATE INDEX IF NOT EXISTS idx_coupon_auto ON coupons(auto_settlement,result_status,expires_at);
CREATE TABLE IF NOT EXISTS delivery_audit (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id),
  delivery_type TEXT NOT NULL CHECK(delivery_type IN ('coupon','result','selftest')),
  coupon_id INTEGER REFERENCES coupons(id),
  telegram_message_id INTEGER,
  status TEXT NOT NULL CHECK(status IN ('sent','failed')),
  detail TEXT,
  sent_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE INDEX IF NOT EXISTS idx_delivery_audit_type ON delivery_audit(delivery_type,sent_at);
CREATE TABLE IF NOT EXISTS settlement_checks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  coupon_id INTEGER NOT NULL REFERENCES coupons(id),
  provider TEXT NOT NULL,
  outcome TEXT NOT NULL CHECK(outcome IN ('won','lost','pending','review','error')),
  message TEXT,
  checked_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE INDEX IF NOT EXISTS idx_settlement_check ON settlement_checks(coupon_id,checked_at);
