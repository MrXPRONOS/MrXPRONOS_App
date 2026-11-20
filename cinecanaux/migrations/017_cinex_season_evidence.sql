-- CinéX: verified season totals from explicitly declared source captions.
-- No manual approval; the GitHub-only switch is mirrored to bot_settings.
-- An episode sequence 1..N is NOT sufficient without expected_episodes.
CREATE TABLE IF NOT EXISTS cine_delivery_season_evidence (
 category TEXT NOT NULL CHECK(category='series'),
 title_key TEXT NOT NULL,
 season_key INTEGER NOT NULL CHECK(season_key BETWEEN 1 AND 50),
 expected_episodes INTEGER NOT NULL CHECK(expected_episodes BETWEEN 1 AND 100),
 observed_at TEXT NOT NULL,
 PRIMARY KEY(category,title_key,season_key)
);
CREATE INDEX IF NOT EXISTS idx_cinex_season_evidence_scan
ON cine_delivery_season_evidence(observed_at,category,season_key);
