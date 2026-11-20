-- CinéX Bot -> conversation Telegram privée du propriétaire.
-- Table stores Telegram references only. Owner's messages are never auto-deleted.
-- Never enable before verifying @CineRadarFr_Bot's bot-only webhook.
CREATE TABLE IF NOT EXISTS cine_owner_vault (
 source_chat_id TEXT NOT NULL CHECK(source_chat_id GLOB '-100[0-9]*'),
 source_message_id INTEGER NOT NULL CHECK(source_message_id > 0),
 media_kind TEXT NOT NULL CHECK(media_kind IN ('poster','video')),
 owner_chat_id INTEGER CHECK(owner_chat_id > 0),
 owner_message_id INTEGER CHECK(owner_message_id > 0),
 status TEXT NOT NULL DEFAULT 'queued' CHECK(status IN ('queued','sending','stored','needs_review','disabled')),
 attempt_count INTEGER NOT NULL DEFAULT 0 CHECK(attempt_count BETWEEN 0 AND 20),
 not_before TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 lock_until TEXT,
 copied_at TEXT,
 error_code TEXT,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY(source_chat_id,source_message_id),
 CHECK((status != 'stored') OR (owner_chat_id IS NOT NULL AND owner_message_id IS NOT NULL))
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_cine_owner_vault_receipt
 ON cine_owner_vault(owner_chat_id,owner_message_id)
 WHERE owner_chat_id IS NOT NULL AND owner_message_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_cine_owner_vault_queue
 ON cine_owner_vault(status,not_before,created_at);
-- Explicit feature gate; default off. No personal Telegram credentials.
INSERT OR IGNORE INTO cine_series_config(setting_key,setting_value)
 VALUES('owner_chat_vault_enabled','false');
