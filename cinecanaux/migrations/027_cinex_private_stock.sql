-- T04. Private Telegram store for owner-approved film references.
-- Source and destination are TELEGRAM message IDs; NO video bytes are stored in D1/GitHub.
-- The destination channel ID stays in D1, never in public GitHub source files.
CREATE TABLE IF NOT EXISTS cine_private_stock_config (
 singleton INTEGER PRIMARY KEY CHECK(singleton=1),
 stock_chat_id TEXT NOT NULL CHECK(stock_chat_id GLOB '-100[0-9]*'),
 owner_id INTEGER NOT NULL CHECK(owner_id>0),
 radar_bot_id INTEGER NOT NULL CHECK(radar_bot_id>0),
 publisher_bot_id INTEGER CHECK(publisher_bot_id IS NULL OR publisher_bot_id>0),
 ready INTEGER NOT NULL DEFAULT 0 CHECK(ready IN(0,1)),
 verified_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS cine_private_stock_items (
 source_chat_id TEXT NOT NULL CHECK(source_chat_id GLOB '-100[0-9]*'),
 source_message_id INTEGER NOT NULL CHECK(source_message_id>0),
 media_kind TEXT NOT NULL DEFAULT 'video' CHECK(media_kind IN ('video','document')),
 source_family TEXT NOT NULL CHECK(source_family IN('classic','franchise','library','series')),
 state TEXT NOT NULL DEFAULT 'queued' CHECK(state IN('queued','sending','stored','needs_review','disabled')),
 stock_message_id INTEGER CHECK(stock_message_id IS NULL OR stock_message_id>0),
 attempt_count INTEGER NOT NULL DEFAULT 0 CHECK(attempt_count BETWEEN 0 AND 10),
 not_before TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 lock_until TEXT,
 error_code TEXT,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY(source_chat_id,source_message_id),
 UNIQUE(stock_message_id),
 CHECK((state != 'stored') OR stock_message_id IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS idx_cinex_stock_queue ON cine_private_stock_items(state,not_before,created_at);
-- No automatic stock deletion; subscriber copies still expire per T03.
