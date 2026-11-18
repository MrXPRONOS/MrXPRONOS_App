-- Operational status for checking verified Telegram channel identity and private delivery.
-- Never store Telegram tokens or private chat IDs here.
CREATE TABLE IF NOT EXISTS radar_ops_status (
 job_name TEXT PRIMARY KEY,
 last_attempt_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 last_success_at TEXT,
 status TEXT NOT NULL DEFAULT 'waiting',
 detail TEXT NOT NULL DEFAULT ''
);
