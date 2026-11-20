-- CinéX -> Ciné Radar: metadata-only catalogue. NO media, bot deliveries, or user data.
-- Explicit library IDs are imported from current GitHub Actions variables, never hardcoded.
CREATE TABLE IF NOT EXISTS cine_delivery_libraries (
 category TEXT PRIMARY KEY CHECK(category IN ('series','action')),
 public_handle TEXT NOT NULL,
 private_chat_id TEXT NOT NULL CHECK(private_chat_id GLOB '-100[0-9]*'),
 rights_attested INTEGER NOT NULL DEFAULT 0 CHECK(rights_attested IN(0,1)),
 owner_access TEXT NOT NULL DEFAULT 'unchecked' CHECK(owner_access IN('unchecked','verified','error')),
 bot_access TEXT NOT NULL DEFAULT 'unchecked' CHECK(bot_access IN('unchecked','verified','not_member','error')),
 observed_videos INTEGER NOT NULL DEFAULT 0,
 last_scanned_at TEXT,
 last_bot_checked_at TEXT,
 updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS cine_delivery_titles (
 title_key TEXT PRIMARY KEY,
 category TEXT NOT NULL REFERENCES cine_delivery_libraries(category) ON DELETE CASCADE,
 normalized_title TEXT NOT NULL,
 display_title TEXT NOT NULL,
 content_kind TEXT NOT NULL CHECK(content_kind IN ('film','series')),
 approval TEXT NOT NULL DEFAULT 'pending_review' CHECK(approval IN('pending_review','approved','blocked')),
 rights_attested INTEGER NOT NULL DEFAULT 0 CHECK(rights_attested IN(0,1)),
 updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE(category,normalized_title,content_kind)
);
CREATE TABLE IF NOT EXISTS cine_delivery_media (
 category TEXT NOT NULL REFERENCES cine_delivery_libraries(category) ON DELETE CASCADE,
 source_message_id INTEGER NOT NULL CHECK(source_message_id>0),
 title_key TEXT NOT NULL REFERENCES cine_delivery_titles(title_key) ON DELETE CASCADE,
 season_number INTEGER CHECK(season_number BETWEEN 1 AND 50),
 episode_number INTEGER CHECK(episode_number BETWEEN 1 AND 999),
 filename TEXT,
 file_size INTEGER CHECK(file_size>=0),
 media_kind TEXT NOT NULL CHECK(media_kind IN('video','document')),
 observed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 availability TEXT NOT NULL DEFAULT 'pending_review' CHECK(availability IN('pending_review','approved','missing','blocked')),
 PRIMARY KEY(category,source_message_id),
 CHECK((season_number IS NULL AND episode_number IS NULL) OR
       (season_number IS NOT NULL AND episode_number IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS idx_cine_delivery_media_title ON cine_delivery_media(title_key,season_number,episode_number);
CREATE INDEX IF NOT EXISTS idx_cine_delivery_titles_status ON cine_delivery_titles(category,approval);
CREATE TABLE IF NOT EXISTS cine_delivery_scans (
 scan_id TEXT PRIMARY KEY,
 scanned_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 series_status TEXT NOT NULL,
 action_status TEXT NOT NULL,
 candidate_count INTEGER NOT NULL DEFAULT 0,
 imported_count INTEGER NOT NULL DEFAULT 0,
 notes TEXT NOT NULL DEFAULT ''
);
-- Stage 1+2 remain inert: no download URLs, /start handler, copyMessages, queues or 24-hour delete.
