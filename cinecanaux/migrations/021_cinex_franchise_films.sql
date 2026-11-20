-- Fast & Furious: a single public channel and one saga poster for several films.
-- Media are indexed from verified Bot API channel posts / owner forwards only.
-- No Telegram user-session credentials or binary storage.
CREATE TABLE IF NOT EXISTS cine_franchise_catalog (
 slug TEXT PRIMARY KEY,
 public_username TEXT NOT NULL UNIQUE,
 title TEXT NOT NULL,
 source_chat_id TEXT UNIQUE CHECK(source_chat_id IS NULL OR source_chat_id GLOB '-100[0-9]*'),
 poster_source_message_id INTEGER CHECK(poster_source_message_id > 0),
 poster_owner_message_id INTEGER CHECK(poster_owner_message_id > 0),
 poster_caption TEXT NOT NULL DEFAULT '',
 token TEXT NOT NULL UNIQUE CHECK(length(token)=24),
 rights_attested INTEGER NOT NULL DEFAULT 1 CHECK(rights_attested IN (0,1)),
 status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','published','needs_review','disabled')),
 public_post_id INTEGER CHECK(public_post_id > 0),
 rescue_post_id INTEGER CHECK(rescue_post_id > 0),
 updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS cine_franchise_films (
 slug TEXT NOT NULL REFERENCES cine_franchise_catalog(slug),
 part INTEGER NOT NULL CHECK(part BETWEEN 1 AND 10),
 source_chat_id TEXT NOT NULL CHECK(source_chat_id GLOB '-100[0-9]*'),
 source_message_id INTEGER NOT NULL CHECK(source_message_id > 0),
 title TEXT NOT NULL DEFAULT '',
 observed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY(slug,part),
 UNIQUE(source_chat_id,source_message_id)
);
CREATE TABLE IF NOT EXISTS cine_franchise_pending (
 owner_message_id INTEGER PRIMARY KEY CHECK(owner_message_id > 0),
 owner_chat_id INTEGER NOT NULL CHECK(owner_chat_id > 0),
 slug TEXT NOT NULL REFERENCES cine_franchise_catalog(slug),
 source_chat_id TEXT NOT NULL CHECK(source_chat_id GLOB '-100[0-9]*'),
 source_message_id INTEGER NOT NULL CHECK(source_message_id > 0),
 caption TEXT NOT NULL DEFAULT '',
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE(source_chat_id,source_message_id)
);
CREATE TABLE IF NOT EXISTS cine_franchise_jobs (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 slug TEXT NOT NULL REFERENCES cine_franchise_catalog(slug),
 telegram_update_id INTEGER NOT NULL UNIQUE,
 telegram_chat_id INTEGER NOT NULL CHECK(telegram_chat_id > 0),
 planned_items INTEGER NOT NULL CHECK(planned_items BETWEEN 1 AND 10),
 delivered_items INTEGER NOT NULL DEFAULT 0,
 status TEXT NOT NULL DEFAULT 'queued' CHECK(status IN ('queued','sending','complete','needs_review')),
 not_before TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 lock_until TEXT,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_cine_franchise_jobs_queue ON cine_franchise_jobs(status,not_before,id);
CREATE INDEX IF NOT EXISTS idx_cine_franchise_jobs_user ON cine_franchise_jobs(telegram_chat_id,created_at);
CREATE TABLE IF NOT EXISTS cine_franchise_job_items (
 job_id INTEGER NOT NULL REFERENCES cine_franchise_jobs(id),
 part INTEGER NOT NULL CHECK(part BETWEEN 1 AND 10),
 source_chat_id TEXT NOT NULL,
 source_message_id INTEGER NOT NULL CHECK(source_message_id > 0),
 state TEXT NOT NULL DEFAULT 'queued' CHECK(state IN ('queued','sending','sent','needs_review')),
 delivered_message_id INTEGER CHECK(delivered_message_id > 0),
 sent_at TEXT,
 delete_after TEXT,
 delete_retry_at TEXT,
 delete_state TEXT NOT NULL DEFAULT 'pending' CHECK(delete_state IN ('pending','retry','deleting','deleted','already_gone','manual_review')),
 delete_lock_until TEXT,
 delete_attempts INTEGER NOT NULL DEFAULT 0,
 delete_last_error TEXT,
 PRIMARY KEY(job_id,part)
);
CREATE INDEX IF NOT EXISTS idx_cine_franchise_item_expiry
 ON cine_franchise_job_items(delete_state,delete_after,delete_retry_at);
-- Explicitly authorized by owner for the linked public channel. One token
-- can be safely published after actual media and poster have been indexed.
INSERT OR IGNORE INTO cine_franchise_catalog(slug,public_username,title,token)
 VALUES('fast-and-furious','fastandfuriousvffr','Fast and Furious — Saga VF',lower(hex(randomblob(12))));
