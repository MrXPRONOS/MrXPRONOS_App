-- Ciné Radar: owner-controlled Telegram announcement audience and delivery ledger.
-- Runtime CREATE TABLE IF NOT EXISTS remains as a backward-compatible bootstrap.
CREATE TABLE IF NOT EXISTS cine_broadcast_subscribers (
 chat_id INTEGER PRIMARY KEY,
 active INTEGER NOT NULL DEFAULT 1,
 blocked INTEGER NOT NULL DEFAULT 0,
 created_at TEXT DEFAULT CURRENT_TIMESTAMP,
 updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS cine_broadcast_jobs (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 owner_id INTEGER NOT NULL,
 text_html TEXT NOT NULL,
 photo_id TEXT NOT NULL DEFAULT '',
 button_text TEXT NOT NULL DEFAULT '',
 button_url TEXT NOT NULL DEFAULT '',
 status TEXT NOT NULL DEFAULT 'draft',
 recipients INTEGER NOT NULL DEFAULT 0,
 delivered INTEGER NOT NULL DEFAULT 0,
 failed INTEGER NOT NULL DEFAULT 0,
 blocked INTEGER NOT NULL DEFAULT 0,
 created_at TEXT DEFAULT CURRENT_TIMESTAMP,
 updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
 lease_until TEXT
);
CREATE TABLE IF NOT EXISTS cine_broadcast_receipts (
 job_id INTEGER NOT NULL,
 chat_id INTEGER NOT NULL,
 state TEXT NOT NULL DEFAULT 'pending',
 attempts INTEGER NOT NULL DEFAULT 0,
 last_error TEXT NOT NULL DEFAULT '',
 retry_at TEXT,
 PRIMARY KEY(job_id,chat_id)
);
CREATE INDEX IF NOT EXISTS idx_cine_broadcast_jobs_queue ON cine_broadcast_jobs(status,lease_until,id);
CREATE INDEX IF NOT EXISTS idx_cine_broadcast_receipts_queue ON cine_broadcast_receipts(job_id,state,retry_at);
