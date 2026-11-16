-- Ciné Radar V2: reliable scheduled-job telemetry and stable Telegram channel identity.
ALTER TABLE channel_index_meta ADD COLUMN telegram_chat_id TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS uq_channel_telegram_chat_id ON channel_index_meta(telegram_chat_id) WHERE telegram_chat_id IS NOT NULL;
CREATE TABLE IF NOT EXISTS automated_job_runs (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 job_name TEXT NOT NULL CHECK(job_name IN ('link_check','discovery','housekeeping')),
 started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 finished_at TEXT,
 status TEXT NOT NULL DEFAULT 'running' CHECK(status IN ('running','success','partial','error')),
 examined INTEGER NOT NULL DEFAULT 0,
 inserted INTEGER NOT NULL DEFAULT 0,
 updated INTEGER NOT NULL DEFAULT 0,
 errors INTEGER NOT NULL DEFAULT 0,
 details TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_automated_job_runs ON automated_job_runs(job_name,started_at DESC);
