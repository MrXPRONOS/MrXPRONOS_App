-- Latence réelle Free Pronos (sans identifiants, IP, contenu de messages, tokens).
CREATE TABLE IF NOT EXISTS perf_samples (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  kind TEXT NOT NULL CHECK (kind IN ('bot_callback','bot_message','miniapp')),
  route TEXT NOT NULL CHECK (length(route) BETWEEN 1 AND 50),
  colo TEXT NOT NULL CHECK (length(colo) BETWEEN 1 AND 4),
  response_ms INTEGER NOT NULL CHECK (response_ms BETWEEN 0 AND 120000),
  telegram_ms INTEGER NOT NULL DEFAULT 0 CHECK (telegram_ms BETWEEN 0 AND 120000),
  callback_ack_ms INTEGER CHECK (callback_ack_ms BETWEEN 0 AND 120000),
  first_reply_ms INTEGER CHECK (first_reply_ms BETWEEN 0 AND 120000),
  telegram_calls INTEGER NOT NULL DEFAULT 0 CHECK (telegram_calls BETWEEN 0 AND 30),
  status TEXT NOT NULL CHECK (status IN ('ok','error')),
  observed_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE INDEX IF NOT EXISTS idx_perf_samples_recent ON perf_samples(observed_at);
