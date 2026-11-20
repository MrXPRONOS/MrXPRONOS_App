-- Classic CinéX downloads issued only for specific verified owner-library videos.
-- Independent of existing Series/Action tables and their constraint history.
CREATE TABLE IF NOT EXISTS cine_classic_links (
 token TEXT PRIMARY KEY CHECK(length(token)=24),
 source_chat_id TEXT NOT NULL CHECK(source_chat_id GLOB '-100[0-9]*'),
 source_message_id INTEGER NOT NULL CHECK(source_message_id>0),
 title TEXT NOT NULL,
 public_handle TEXT NOT NULL,
 public_poster_message_id INTEGER,
 public_video_message_id INTEGER,
 status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN('pending','published','disabled')),
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE(source_chat_id,source_message_id)
);
CREATE INDEX IF NOT EXISTS idx_cine_classic_links_status ON cine_classic_links(status,source_message_id);
CREATE TABLE IF NOT EXISTS cine_classic_deliveries (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 token TEXT NOT NULL REFERENCES cine_classic_links(token),
 telegram_update_id INTEGER NOT NULL UNIQUE,
 telegram_chat_id INTEGER NOT NULL CHECK(telegram_chat_id>0),
 status TEXT NOT NULL DEFAULT 'queued' CHECK(status IN('queued','sending','sent','needs_review','deleted')),
 delivered_message_id INTEGER,
 lock_until TEXT,
 sent_at TEXT,
 delete_after TEXT,
 delete_retry_at TEXT,
 delete_state TEXT NOT NULL DEFAULT 'pending' CHECK(delete_state IN('pending','retry','deleting','deleted','already_gone','manual_review')),
 delete_lock_until TEXT,
 delete_attempts INTEGER NOT NULL DEFAULT 0,
 delete_last_error TEXT,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_cine_classic_queue ON cine_classic_deliveries(status,created_at);
CREATE INDEX IF NOT EXISTS idx_cine_classic_expiry ON cine_classic_deliveries(delete_state,delete_after);
