-- Manual Telegram source inbox: owner-approved, rights-gated, webhook-only.
-- Stores metadata and Telegram message references, never video bytes or tokens.
-- Disabled unless CINEX_MANUAL_INBOX_ENABLED is set on the Worker.
CREATE TABLE IF NOT EXISTS cine_manual_fallback_sources (
 chat_id TEXT PRIMARY KEY CHECK(chat_id GLOB '-100[0-9]*'),
 category TEXT NOT NULL CHECK(category IN
 ('films','series','animes','comedie','action','desir',
  'formation_general','formation_business','formation_finance',
  'formation_digitale','formation_mindset')),
 rights_attested INTEGER NOT NULL DEFAULT 0 CHECK(rights_attested IN(0,1)),
 bot_access_verified INTEGER NOT NULL DEFAULT 0 CHECK(bot_access_verified IN(0,1)),
 owner_approved INTEGER NOT NULL DEFAULT 0 CHECK(owner_approved IN(0,1)),
 enabled INTEGER NOT NULL DEFAULT 0 CHECK(enabled IN(0,1)),
 verified_at TEXT,
 CHECK(enabled=0 OR (rights_attested=1 AND bot_access_verified=1 AND owner_approved=1))
);
CREATE TABLE IF NOT EXISTS cine_manual_fallback_inbox (
 chat_id TEXT NOT NULL CHECK(chat_id GLOB '-100[0-9]*'),
 message_id INTEGER NOT NULL CHECK(message_id>0),
 category TEXT NOT NULL,
 kind TEXT NOT NULL CHECK(kind IN ('poster','video','course_file','text')),
 file_unique_id TEXT NOT NULL DEFAULT '',
 filename TEXT NOT NULL DEFAULT '',
 mime_type TEXT NOT NULL DEFAULT '',
 bytes INTEGER NOT NULL DEFAULT 0,
 caption TEXT NOT NULL DEFAULT '',
 grouped_id TEXT NOT NULL DEFAULT '',
 posted_at INTEGER NOT NULL DEFAULT 0,
 state TEXT NOT NULL DEFAULT 'indexed'
 CHECK(state IN ('indexed','needs_review','published')),
 review_code TEXT NOT NULL DEFAULT '',
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY(chat_id,message_id),
 FOREIGN KEY(chat_id) REFERENCES cine_manual_fallback_sources(chat_id)
);
CREATE TABLE IF NOT EXISTS cine_manual_fallback_receipts (
 category TEXT NOT NULL,
 content_key TEXT NOT NULL,
 stage TEXT NOT NULL CHECK(stage IN
 ('central_stock','private_poster','private_video','private_index',
  'public_poster','public_video','formation_file')),
 status TEXT NOT NULL CHECK(status IN
 ('reserved','inflight','uncertain','complete')),
 target_chat_id TEXT NOT NULL,
 source_chat_id TEXT NOT NULL,
 source_message_id INTEGER NOT NULL,
 target_message_id INTEGER,
 updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY(category,content_key,stage),
 CHECK(target_message_id IS NULL OR target_message_id>0)
);
CREATE INDEX IF NOT EXISTS idx_cine_manual_inbox_category
 ON cine_manual_fallback_inbox(category,state,posted_at,message_id);
CREATE INDEX IF NOT EXISTS idx_cine_manual_inbox_unique
 ON cine_manual_fallback_inbox(file_unique_id) WHERE file_unique_id!='';
CREATE INDEX IF NOT EXISTS idx_cine_manual_receipts_status
 ON cine_manual_fallback_receipts(status,updated_at);
