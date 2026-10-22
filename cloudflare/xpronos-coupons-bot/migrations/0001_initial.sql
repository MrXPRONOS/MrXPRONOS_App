-- XPRONOS 4+ Cloudflare D1 — SQLite, independent de Supabase.
-- Les triggers maintiennent les soldes XP et le stock dans la même transaction.
-- Ne jamais executer cette migration sur le projet Supabase.

CREATE TABLE IF NOT EXISTS users (
 id INTEGER PRIMARY KEY CHECK(id > 0),
 name TEXT NOT NULL DEFAULT 'Membre',
 referred_by INTEGER REFERENCES users(id),
 adult_confirmed INTEGER NOT NULL DEFAULT 0 CHECK(adult_confirmed IN (0,1)),
 required_verified INTEGER NOT NULL DEFAULT 0 CHECK(required_verified IN (0,1)),
 referral_rewarded INTEGER NOT NULL DEFAULT 0 CHECK(referral_rewarded IN (0,1)),
 xp INTEGER NOT NULL DEFAULT 0 CHECK(xp >= 0),
 bonus_last_at TEXT,
 bonus_day TEXT,
 bonus_day_total INTEGER NOT NULL DEFAULT 0 CHECK(bonus_day_total >= 0),
 created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE IF NOT EXISTS tasks (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 chat_id TEXT NOT NULL UNIQUE,
 url TEXT NOT NULL,
 xp INTEGER NOT NULL CHECK(xp > 0 AND xp <= 100000),
 active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1))
);

CREATE TABLE IF NOT EXISTS task_claims (
 user_id INTEGER NOT NULL REFERENCES users(id),
 task_id INTEGER NOT NULL REFERENCES tasks(id),
 claimed_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
 PRIMARY KEY (user_id,task_id)
);

CREATE TABLE IF NOT EXISTS coupons (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 tier TEXT NOT NULL CHECK(tier IN ('SIMPLE','PRO','VIP')),
 title TEXT NOT NULL,
 selections TEXT NOT NULL CHECK(json_valid(selections)),
 total_odds TEXT NOT NULL CHECK(CAST(total_odds AS REAL) >= 4),
 xp_cost INTEGER NOT NULL CHECK(xp_cost >= 0 AND xp_cost <= 100000),
 expires_at TEXT NOT NULL,
 stock INTEGER NOT NULL DEFAULT -1 CHECK(stock >= -1),
 active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
 created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE IF NOT EXISTS redemptions (
 user_id INTEGER NOT NULL REFERENCES users(id),
 coupon_id INTEGER NOT NULL REFERENCES coupons(id),
 snapshot TEXT NOT NULL CHECK(json_valid(snapshot)),
 xp_spent INTEGER NOT NULL CHECK(xp_spent >= 0),
 claimed_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
 PRIMARY KEY(user_id,coupon_id)
);

CREATE TABLE IF NOT EXISTS ledger (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 user_id INTEGER NOT NULL REFERENCES users(id),
 delta INTEGER NOT NULL,
 reason TEXT NOT NULL,
 created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE IF NOT EXISTS manual_grants (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 user_id INTEGER NOT NULL REFERENCES users(id),
 xp INTEGER NOT NULL CHECK(xp > 0 AND xp <= 100000),
 update_id INTEGER NOT NULL UNIQUE
);

CREATE INDEX IF NOT EXISTS idx_coupons_live ON coupons(active,expires_at);

CREATE INDEX IF NOT EXISTS idx_users_referrals ON users(referred_by);

CREATE INDEX IF NOT EXISTS idx_ledger_user ON ledger(user_id,created_at);

CREATE TRIGGER IF NOT EXISTS trg_referral_reward AFTER UPDATE OF referral_rewarded ON users
 WHEN OLD.referral_rewarded=0 AND NEW.referral_rewarded=1 AND NEW.referred_by IS NOT NULL
 BEGIN
 UPDATE users SET xp=xp+30 WHERE id=NEW.referred_by;
 INSERT INTO ledger(user_id,delta,reason) VALUES(NEW.referred_by,30,'referral:'||NEW.id);
 END;

CREATE TRIGGER IF NOT EXISTS trg_task_claim AFTER INSERT ON task_claims
 BEGIN
 UPDATE users SET xp=xp+(SELECT xp FROM tasks WHERE id=NEW.task_id) WHERE id=NEW.user_id;
 INSERT INTO ledger(user_id,delta,reason) SELECT NEW.user_id,xp,'task:'||NEW.task_id FROM tasks WHERE id=NEW.task_id;
 END;

CREATE TRIGGER IF NOT EXISTS trg_bonus AFTER UPDATE OF bonus_last_at ON users
 WHEN NEW.bonus_last_at IS NOT OLD.bonus_last_at
 BEGIN
 INSERT INTO ledger(user_id,delta,reason) VALUES(NEW.id,5,'bonus');
 END;

CREATE TRIGGER IF NOT EXISTS trg_redeem AFTER INSERT ON redemptions
 BEGIN
 UPDATE users SET xp=xp-NEW.xp_spent WHERE id=NEW.user_id;
 UPDATE coupons SET stock=stock-1 WHERE id=NEW.coupon_id AND stock>0;
 INSERT INTO ledger(user_id,delta,reason) VALUES(NEW.user_id,-NEW.xp_spent,'coupon:'||NEW.coupon_id);
 END;

CREATE TRIGGER IF NOT EXISTS trg_manual_grant AFTER INSERT ON manual_grants
 BEGIN
 UPDATE users SET xp=xp+NEW.xp WHERE id=NEW.user_id;
 INSERT INTO ledger(user_id,delta,reason) VALUES(NEW.user_id,NEW.xp,'admin');
 END;
