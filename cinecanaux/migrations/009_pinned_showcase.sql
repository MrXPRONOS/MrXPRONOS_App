-- Messages mis en avant à partir des épingles Telegram officielles.
-- Stockage de métadonnées et de file_id d'images uniquement (jamais de vidéos).
CREATE TABLE IF NOT EXISTS cine_pinned_posts (
  kind TEXT NOT NULL CHECK(kind IN ('films','series','animes')),
  chat_id TEXT NOT NULL,
  message_id INTEGER NOT NULL CHECK(message_id > 0),
  title TEXT NOT NULL DEFAULT '',
  caption TEXT NOT NULL DEFAULT '',
  image_file_id TEXT NOT NULL DEFAULT '',
  media_kind TEXT NOT NULL DEFAULT 'photo' CHECK(media_kind IN ('photo','video','text')),
  source TEXT NOT NULL CHECK(source IN ('getchat','pin_event','owner_forward')),
  first_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  click_count INTEGER NOT NULL DEFAULT 0,
  active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
  PRIMARY KEY(kind,message_id)
);
CREATE INDEX IF NOT EXISTS idx_cine_pins_order ON cine_pinned_posts(active,kind,click_count,last_seen_at);
CREATE TABLE IF NOT EXISTS cine_pins_poll (
  kind TEXT PRIMARY KEY CHECK(kind IN ('films','series','animes')),
  last_attempt_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_success_at TEXT,
  detail TEXT NOT NULL DEFAULT ''
);
