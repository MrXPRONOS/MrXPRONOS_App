-- 12-hour public video expiry journal for bot-only manual fallback.
-- The original public Telegram message ID is copied from a completed send
-- receipt; never invent IDs or retry an ambiguous deletion.
CREATE TABLE IF NOT EXISTS cine_manual_fallback_expiries (
 category TEXT NOT NULL,
 content_key TEXT NOT NULL,
 target_chat_id TEXT NOT NULL CHECK(target_chat_id GLOB '-100[0-9]*'),
 target_message_id INTEGER NOT NULL CHECK(target_message_id>0),
 not_before TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN('pending','deleting','uncertain','deleted')),
 error_code TEXT NOT NULL DEFAULT '',
 updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY(category,content_key)
);
CREATE INDEX IF NOT EXISTS idx_cine_manual_fallback_expiries
 ON cine_manual_fallback_expiries(status,not_before);
