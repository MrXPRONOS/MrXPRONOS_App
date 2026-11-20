-- T03: heartbeat and factual deletion outcomes for four private-copy families.
-- No Telegram user ID, bot token, channel ID, message ID or content is saved here.
-- Worker also creates this table lazily so deployment does not require a
-- manual change to the existing D1 database.
CREATE TABLE IF NOT EXISTS cine_cleanup_health (
 family TEXT PRIMARY KEY CHECK(family IN ('libraries','series','classics','franchise')),
 status TEXT NOT NULL DEFAULT 'waiting' CHECK(status IN ('waiting','ok','error')),
 last_attempt_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 last_success_at TEXT,
 last_error TEXT NOT NULL DEFAULT '',
 last_deleted INTEGER NOT NULL DEFAULT 0,
 last_already_gone INTEGER NOT NULL DEFAULT 0,
 last_retried INTEGER NOT NULL DEFAULT 0,
 last_manual_review INTEGER NOT NULL DEFAULT 0,
 last_overdue INTEGER NOT NULL DEFAULT 0,
 last_backfilled INTEGER NOT NULL DEFAULT 0,
 run_count INTEGER NOT NULL DEFAULT 0
);
