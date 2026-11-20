-- CinéX séries individuelles : bibliothèque indexée uniquement par événements Bot API.
-- Aucune session utilisateur, aucun stockage de vidéo binaire.
-- Droits et autorisation de livraison désactivés par défaut.
CREATE TABLE IF NOT EXISTS cine_series_channels (
 chat_id TEXT PRIMARY KEY CHECK(chat_id GLOB '-100[0-9]*'),
 title TEXT NOT NULL DEFAULT '',
 publisher_access TEXT NOT NULL DEFAULT 'unchecked',
 radar_access TEXT NOT NULL DEFAULT 'unchecked',
 rights_attested INTEGER NOT NULL DEFAULT 0 CHECK(rights_attested IN(0,1)),
 enabled INTEGER NOT NULL DEFAULT 1 CHECK(enabled IN(0,1)),
 verified_at TEXT,
 updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS cine_series_posters (
 chat_id TEXT NOT NULL REFERENCES cine_series_channels(chat_id),
 season INTEGER NOT NULL CHECK(season BETWEEN 1 AND 50),
 source_message_id INTEGER NOT NULL CHECK(source_message_id>0),
 caption TEXT NOT NULL DEFAULT '',
 observed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY(chat_id,season),
 UNIQUE(chat_id,source_message_id)
);
CREATE TABLE IF NOT EXISTS cine_series_seasons (
 chat_id TEXT NOT NULL REFERENCES cine_series_channels(chat_id),
 season INTEGER NOT NULL CHECK(season BETWEEN 1 AND 50),
 expected_episodes INTEGER CHECK(expected_episodes BETWEEN 1 AND 100),
 observed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY(chat_id,season)
);
CREATE TABLE IF NOT EXISTS cine_series_episodes (
 chat_id TEXT NOT NULL REFERENCES cine_series_channels(chat_id),
 season INTEGER NOT NULL CHECK(season BETWEEN 1 AND 50),
 episode INTEGER NOT NULL CHECK(episode BETWEEN 1 AND 100),
 source_message_id INTEGER NOT NULL CHECK(source_message_id>0),
 observed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY(chat_id,season,episode),
 UNIQUE(chat_id,source_message_id)
);
CREATE INDEX IF NOT EXISTS idx_cine_series_media ON cine_series_episodes(chat_id,season,episode);
CREATE TABLE IF NOT EXISTS cine_series_publications (
 token TEXT PRIMARY KEY CHECK(length(token)=24),
 chat_id TEXT NOT NULL UNIQUE REFERENCES cine_series_channels(chat_id),
 public_post_id INTEGER,
 rescue_post_id INTEGER,
 state TEXT NOT NULL DEFAULT 'pending' CHECK(state IN('pending','published','needs_review','disabled')),
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS cine_series_config (
 setting_key TEXT PRIMARY KEY,
 setting_value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS cine_series_jobs (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 token TEXT NOT NULL REFERENCES cine_series_publications(token),
 telegram_chat_id INTEGER NOT NULL CHECK(telegram_chat_id>0),
 telegram_update_id INTEGER NOT NULL UNIQUE,
 status TEXT NOT NULL DEFAULT 'queued' CHECK(status IN('queued','sending','complete','needs_review')),
 planned_items INTEGER NOT NULL CHECK(planned_items BETWEEN 1 AND 300),
 delivered_items INTEGER NOT NULL DEFAULT 0,
 not_before TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 lock_until TEXT,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_cine_series_jobs ON cine_series_jobs(status,not_before,id);
CREATE INDEX IF NOT EXISTS idx_cine_series_jobs_user ON cine_series_jobs(telegram_chat_id,created_at);
CREATE TABLE IF NOT EXISTS cine_series_job_items (
 job_id INTEGER NOT NULL REFERENCES cine_series_jobs(id) ON DELETE CASCADE,
 ordinal INTEGER NOT NULL CHECK(ordinal BETWEEN 1 AND 300),
 source_chat_id TEXT NOT NULL,
 source_message_id INTEGER NOT NULL,
 delivered_message_id INTEGER,
 state TEXT NOT NULL DEFAULT 'queued' CHECK(state IN('queued','sending','sent','needs_review')),
 sent_at TEXT,
 delete_after TEXT,
 delete_retry_at TEXT,
 delete_state TEXT NOT NULL DEFAULT 'pending' CHECK(delete_state IN('pending','retry','deleting','deleted','already_gone','manual_review')),
 delete_lock_until TEXT,
 delete_attempts INTEGER NOT NULL DEFAULT 0,
 delete_last_error TEXT,
 PRIMARY KEY(job_id,ordinal)
);
CREATE INDEX IF NOT EXISTS idx_cine_series_expiry ON cine_series_job_items(delete_state,delete_after,delete_retry_at);
