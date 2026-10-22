-- Free Pronos V2. D1 SQLite. Uniquement dans la base du bot.
-- Cohérence XP: toutes les écritures d'engagement sont uniques et atomiques.
CREATE TABLE IF NOT EXISTS user_preferences (
  user_id INTEGER PRIMARY KEY REFERENCES users(id),
  notify_coupons INTEGER NOT NULL DEFAULT 0 CHECK (notify_coupons IN (0,1)),
  notify_results INTEGER NOT NULL DEFAULT 0 CHECK (notify_results IN (0,1)),
  updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE TABLE IF NOT EXISTS engagement_claims (
  user_id INTEGER NOT NULL REFERENCES users(id),
  kind TEXT NOT NULL CHECK(kind IN ('daily','weekly')),
  period_key TEXT NOT NULL,
  xp INTEGER NOT NULL CHECK(xp IN (3,10)),
  claimed_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  PRIMARY KEY (user_id,kind,period_key)
);
CREATE TRIGGER IF NOT EXISTS trg_engagement_claim AFTER INSERT ON engagement_claims
BEGIN
  UPDATE users SET xp=xp+NEW.xp WHERE id=NEW.user_id;
  INSERT INTO ledger(user_id,delta,reason)
    VALUES(NEW.user_id,NEW.xp,NEW.kind||':'||NEW.period_key);
END;
CREATE TABLE IF NOT EXISTS processed_updates (
  update_id INTEGER PRIMARY KEY,
  received_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE INDEX IF NOT EXISTS idx_processed_received ON processed_updates(received_at);
CREATE TABLE IF NOT EXISTS coupon_notifications (
  user_id INTEGER NOT NULL REFERENCES users(id),
  coupon_id INTEGER NOT NULL REFERENCES coupons(id),
  kind TEXT NOT NULL CHECK(kind IN ('new','result')),
  sent_at TEXT,
  PRIMARY KEY(user_id,coupon_id,kind)
);
CREATE INDEX IF NOT EXISTS idx_notifications_pending ON coupon_notifications(kind,sent_at);
ALTER TABLE coupons ADD COLUMN result_status TEXT NOT NULL DEFAULT 'available'
  CHECK(result_status IN ('available','live','won','lost','void'));
ALTER TABLE coupons ADD COLUMN result_reviewed_at TEXT;
ALTER TABLE coupons ADD COLUMN result_source TEXT;
CREATE INDEX IF NOT EXISTS idx_coupon_results ON coupons(result_status,result_reviewed_at);
