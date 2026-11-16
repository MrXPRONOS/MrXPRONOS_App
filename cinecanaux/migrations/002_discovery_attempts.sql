-- Fair scheduling for repeated discovery attempts.
-- Keep retry history separate from the public channel index.
CREATE TABLE IF NOT EXISTS discovery_attempts (
 username TEXT PRIMARY KEY COLLATE NOCASE,
 attempts INTEGER NOT NULL DEFAULT 0,
 last_attempt_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 last_outcome TEXT NOT NULL DEFAULT 'unverifiable'
);
CREATE INDEX IF NOT EXISTS idx_discovery_attempt_time ON discovery_attempts(last_attempt_at);
