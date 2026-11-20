-- CINEX V1. Stages 3/4 delivery; no files or raw video bytes are stored in D1.
-- Explicit human approval of each licensed film/season is required.
CREATE TABLE IF NOT EXISTS cine_delivery_links (
 token TEXT PRIMARY KEY CHECK(length(token)=24),
 title_key TEXT NOT NULL REFERENCES cine_delivery_titles(title_key) ON DELETE CASCADE,
 category TEXT NOT NULL CHECK(category IN ('series','action')),
 season_key INTEGER NOT NULL DEFAULT 0 CHECK(season_key BETWEEN 0 AND 50),
 enabled INTEGER NOT NULL DEFAULT 0 CHECK(enabled IN (0,1)),
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE(category,title_key,season_key)
);
CREATE INDEX IF NOT EXISTS idx_cine_delivery_links_title ON cine_delivery_links(title_key,enabled);
CREATE TABLE IF NOT EXISTS cine_delivery_jobs (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 token TEXT NOT NULL REFERENCES cine_delivery_links(token),
 telegram_chat_id INTEGER NOT NULL,
 telegram_update_id INTEGER NOT NULL UNIQUE,
 status TEXT NOT NULL DEFAULT 'queued'
  CHECK(status IN('queued','sending','complete','failed','needs_review')),
 planned_items INTEGER NOT NULL CHECK(planned_items BETWEEN 1 AND 100),
 delivered_items INTEGER NOT NULL DEFAULT 0,
 not_before TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 lock_until TEXT,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_cine_delivery_jobs_queue ON cine_delivery_jobs(status,not_before,created_at);
CREATE INDEX IF NOT EXISTS idx_cine_delivery_jobs_user ON cine_delivery_jobs(telegram_chat_id,created_at);
CREATE TABLE IF NOT EXISTS cine_delivery_job_items (
 job_id INTEGER NOT NULL REFERENCES cine_delivery_jobs(id) ON DELETE CASCADE,
 ordinal INTEGER NOT NULL,
 source_chat_id TEXT NOT NULL,
 source_message_id INTEGER NOT NULL,
 delivered_message_id INTEGER,
 state TEXT NOT NULL DEFAULT 'queued'
  CHECK(state IN('queued','sending','sent','needs_review')),
 attempts INTEGER NOT NULL DEFAULT 0,
 sent_at TEXT,
 PRIMARY KEY(job_id,ordinal)
);
CREATE INDEX IF NOT EXISTS idx_cine_delivery_job_items_state ON cine_delivery_job_items(state,job_id);
-- Expiry/deletion belongs to stage 6. This migration does not delete any messages.
