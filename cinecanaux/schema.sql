-- Ciné Radar : uniquement annuaire, découverte automatique et aperçus publics.
CREATE TABLE IF NOT EXISTS channels (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 title TEXT NOT NULL,
 link TEXT NOT NULL UNIQUE,
 description TEXT NOT NULL DEFAULT '',
 content_type TEXT NOT NULL CHECK (content_type IN ('films','series','animes')),
 genre TEXT NOT NULL DEFAULT 'general',
 status TEXT NOT NULL DEFAULT 'approved',
 rights_confirmed INTEGER NOT NULL DEFAULT 0,
 language TEXT NOT NULL DEFAULT 'VF',
 verified_at TEXT,
 updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_channels_lookup ON channels(status,content_type,updated_at);
CREATE TABLE IF NOT EXISTS discovery_candidates (
 username TEXT PRIMARY KEY COLLATE NOCASE,
 title TEXT NOT NULL,link TEXT NOT NULL,
 content_type TEXT NOT NULL CHECK (content_type IN ('films','series','animes')),
 genre TEXT NOT NULL,source_category TEXT NOT NULL,
 matching_pairs INTEGER NOT NULL DEFAULT 0,
 technical_status TEXT NOT NULL CHECK(technical_status IN ('qualified','rejected_format')),
 rights_status TEXT NOT NULL DEFAULT 'unverified',
 first_seen TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 last_seen TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 last_scan TEXT NOT NULL,
 updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_discovery_lookup ON discovery_candidates(technical_status,rights_status);
CREATE TABLE IF NOT EXISTS discovery_sync_status (
 id INTEGER PRIMARY KEY CHECK(id=1),
 scan_date TEXT NOT NULL,
 imported INTEGER NOT NULL DEFAULT 0,
 qualified INTEGER NOT NULL DEFAULT 0,
 rejected INTEGER NOT NULL DEFAULT 0,
 last_error TEXT NOT NULL DEFAULT '',
 updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS bot_webhook_status (
 id INTEGER PRIMARY KEY CHECK(id=1),
 status TEXT NOT NULL,
 detail TEXT NOT NULL DEFAULT '',
 updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS bot_settings (
 setting_key TEXT PRIMARY KEY,
 value TEXT NOT NULL,
 updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS channel_telemetry (
 channel_id INTEGER PRIMARY KEY,
 check_status TEXT NOT NULL DEFAULT 'unknown',
 last_checked_at TEXT,
 last_good_at TEXT
);
CREATE TABLE IF NOT EXISTS channel_profile_cache (
 channel_id INTEGER PRIMARY KEY,
 title TEXT,
 description TEXT,
 avatar_url TEXT,
 post_image_url TEXT,
 last_post_at TEXT,
 preview_status TEXT NOT NULL DEFAULT 'unavailable',
 checked_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
-- L'ancien compte administrateur peut être conservé pour un futur outil de gestion,
-- mais il n'y a plus d'espace administrateur dans l'interface publique.
CREATE TABLE IF NOT EXISTS admin_users (
 user_id INTEGER PRIMARY KEY,
 role TEXT NOT NULL DEFAULT 'admin',
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
-- Une migration D1 retire séparément les anciennes tables utilisateur.
