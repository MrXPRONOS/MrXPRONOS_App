-- Ciné Radar : tendances, canaux principaux et rapprochement de publications.
-- Les fichiers vidéo ne sont ni stockés ni téléchargés.
CREATE TABLE IF NOT EXISTS radar_primary_channels (
 kind TEXT PRIMARY KEY CHECK(kind IN ('films','series','animes')),
 username TEXT NOT NULL UNIQUE,
 chat_id TEXT UNIQUE,
 updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
INSERT INTO radar_primary_channels(kind,username) VALUES
 ('films','CineXFilms_vf'),('series','seriesvf_cinex'),('animes','CineXAnimeFR')
 ON CONFLICT(kind) DO UPDATE SET username=excluded.username,updated_at=CURRENT_TIMESTAMP;

CREATE TABLE IF NOT EXISTS radar_titles (
 id TEXT PRIMARY KEY,
 kind TEXT NOT NULL CHECK(kind IN ('films','series','animes')),
 title TEXT NOT NULL,
 title_original TEXT NOT NULL DEFAULT '',
 aliases TEXT NOT NULL DEFAULT '',
 summary TEXT NOT NULL DEFAULT '',
 year INTEGER,
 poster_url TEXT NOT NULL DEFAULT '',
 source_url TEXT NOT NULL DEFAULT '',
 source TEXT NOT NULL,
 trend_rank INTEGER NOT NULL DEFAULT 100,
 first_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 last_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 click_count INTEGER NOT NULL DEFAULT 0,
 last_clicked_at TEXT,
 authorized INTEGER NOT NULL DEFAULT 0 CHECK(authorized IN (0,1))
);
CREATE INDEX IF NOT EXISTS idx_radar_titles_kind_rank ON radar_titles(kind,trend_rank,last_seen_at);

CREATE TABLE IF NOT EXISTS radar_posts (
 chat_id TEXT NOT NULL,
 message_id INTEGER NOT NULL,
 kind TEXT NOT NULL CHECK(kind IN ('films','series','animes')),
 username TEXT NOT NULL,
 caption TEXT NOT NULL DEFAULT '',
 media_kind TEXT NOT NULL CHECK(media_kind IN ('video','photo','text')),
 posted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY(chat_id,message_id)
);
CREATE INDEX IF NOT EXISTS idx_radar_posts_kind_time ON radar_posts(kind,updated_at);

CREATE TABLE IF NOT EXISTS radar_matches (
 title_id TEXT NOT NULL REFERENCES radar_titles(id) ON DELETE CASCADE,
 chat_id TEXT NOT NULL,
 message_id INTEGER NOT NULL,
 kind TEXT NOT NULL,
 message_url TEXT NOT NULL,
 confidence INTEGER NOT NULL DEFAULT 0,
 media_kind TEXT NOT NULL,
 matched_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY(title_id,chat_id,message_id),
 FOREIGN KEY(chat_id,message_id) REFERENCES radar_posts(chat_id,message_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_radar_matches_title ON radar_matches(title_id,confidence,matched_at);
CREATE TABLE IF NOT EXISTS radar_runs (
 job_name TEXT PRIMARY KEY,
 last_success_at TEXT,
 last_attempt_at TEXT,
 last_error TEXT NOT NULL DEFAULT '',
 last_count INTEGER NOT NULL DEFAULT 0
);
